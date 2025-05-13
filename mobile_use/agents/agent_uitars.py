import logging
from typing import Iterator
import os
import pickle
import gzip
import io

from mobile_use.scheme import *
from mobile_use.environ import Environment
from mobile_use.vlm import VLMWrapper
from mobile_use.utils import encode_image_url, smart_resize, remove_img_placeholder
from mobile_use.agents import Agent

from mobile_use.agents.sub_agent import Planner, UITARSOperator, Reflector, NoteTaker, Processor, Evolutor


logger = logging.getLogger(__name__)


INIT_TIPS = """- If the task is finished, you should terminate the task in time!
- If you stuck in an action, you should try to change the action or the correspoinding parameters. Do not always repeat the same action!
- Sometimes there is some default text in the text field you want to type in, remember to delete them before typing.
- To delete some text, you can place the cursor at the right place and long press the backspace to delete all the text."""

ANSWER_PROMPT_TEMPLATE = """
The (overall) user query is: {goal}
Now you have finished the task. I want you to provide an answer to the user query.
Answer with the following format:

## Output Format
```\nThought: ...
Action: answer(content='') ## Put you answer in the `content` parameter.\n```
"""

def show_message(messages: List[dict], name: str = None):
    name = f"{name} " if name is not None else ""
    logger.info(f"==============={name}MESSAGE==============")
    for message in messages:
        logger.info(f"ROLE: {message['role']}")
        for content in message['content']:
            if content['type'] == 'text':
                logger.info(f"TEXT:")
                logger.info(content['text'])
            else:
                logger.info(f"{content['type']}: SKIP.")
    logger.info(f"==============={name}MESSAGE END==============")

def _unzip_and_read_pickle(file_path: str) -> Any:
  """Reads a gzipped pickle file using 'with open', unzips, and unpickles it.

  Args:
      file_path: The path to the gzipped pickle file.

  Returns:
      The original Python object that was pickled and gzipped.
  """
  with open(file_path, 'rb') as f:
    compressed = f.read()

  with gzip.open(io.BytesIO(compressed), 'rb') as f_in:
    return pickle.load(f_in)

def recover_tips(log_dir: str):
    if not log_dir:
        logger.info("Load the initial tips since the log directory is not provided.")
        return INIT_TIPS
    if not os.path.exists(log_dir):
        logger.info(f"Load the initial tips since the log directory {log_dir} does not exist.")
        return INIT_TIPS
    files = os.listdir(log_dir)
    if not files:
        logger.info(f"Load the initial tips since the log directory {log_dir} is empty.")
        return INIT_TIPS
    files = [file for file in files if os.path.getsize(os.path.join(log_dir, file)) >= 10*1024]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(log_dir, x)), reverse=True)
    for file in files:
        data = _unzip_and_read_pickle(os.path.join(log_dir, file))
        latest_tips = data[0]['episode_data'].get('output_tips', None)
        latest_tips = latest_tips[0] if latest_tips else None
        if latest_tips:
            logger.info(f"Load the latest tips from the log file {file}.")
            logger.info(f"TIPS: {latest_tips}")
            return latest_tips
    logger.info(f"Load the initial tips since no valid tips are found in the log directory {log_dir}.")
    return INIT_TIPS

@Agent.register('UITARSAgent')
class UITARSAgent(Agent):
    def __init__(
            self, 
            env: Environment,
            vlm: VLMWrapper,
            max_steps: int=10,
            num_latest_screenshot: int=10,
            num_histories: int = None,
            max_reflection_action: int=3,
            reflection_action_waiting_seconds: float=1.0,
            max_retry_vlm: int=3,
            retry_vlm_waiting_seconds: float=1.0,
            use_planner: bool=False,
            use_reflector: bool=False,
            use_note_taker: bool=False,
            use_processor: bool=False,
            use_evolutor: bool=False,
            log_dir: str=None,
        ):
        super().__init__(env=env, vlm=vlm, max_steps=max_steps)
        self.num_latest_screenshot = num_latest_screenshot
        self.num_histories = num_histories
        self.max_reflection_action = max_reflection_action
        self.reflection_action_waiting_seconds = reflection_action_waiting_seconds
        self.max_retry_vlm = max_retry_vlm
        self.retry_vlm_waiting_seconds = retry_vlm_waiting_seconds
        self.log_dir = log_dir

        self.use_planner = use_planner
        self.use_reflector = use_reflector
        self.use_note_taker = use_note_taker
        self.use_processor = use_processor
        self.use_evolutor = use_evolutor

        self.enable_multi_model = False
        if self.use_planner or self.use_reflector or self.use_note_taker or self.use_processor or self.use_evolutor:
            self.enable_multi_model = True

        self.planner = Planner()
        self.operator = UITARSOperator(enable_multi_model=self.enable_multi_model)
        self.reflector = Reflector()
        self.note_taker = NoteTaker()
        self.processor = Processor()
        self.evolutor = Evolutor()

        self.tips = recover_tips(self.log_dir)

    def reset(self, goal: str='') -> None:
        """Reset the state of the agent.
        """
        self._init_data(goal=goal)
        self.planner = Planner()
        self.operator = UITARSOperator(enable_multi_model=self.enable_multi_model)
        self.reflector = Reflector()
        self.note_taker = NoteTaker()
        self.processor = Processor()
        self.evolutor = Evolutor()

    def _get_curr_step_data(self) -> StepData:
        if len(self.trajectory) > self.curr_step_idx:
            return self.trajectory[self.curr_step_idx]
        else:
            return None

    def step(self):
        """Execute the task with maximum number of steps.

        Returns: Answer
        """
        logger.info("Step %d ... ..." % self.curr_step_idx)
        if self.curr_step_idx >= 80:
            raise Exception("The agent has performed too many steps. Stop to avoid OOM ERROR.")
        answer = None
        show_step = [0,3]

        # Get the current environment screen
        env_state = self.env.get_state()
        pixels = env_state.pixels
        resized_height, resized_width = smart_resize(height=pixels.height, width=pixels.width)

        # Add new step data
        if len(self.trajectory) == 0:
            self.episode_data.input_tips = self.tips
        self.trajectory.append(StepData(
            step_idx=self.curr_step_idx,
            curr_env_state=env_state,
            vlm_call_history=[]
        ))
        step_data = self.trajectory[-1]

        # Call planner
        if self.use_planner:
            plan_messages = self.planner.get_message(self.episode_data)
            plan_messages = remove_img_placeholder(plan_messages)
            if self.curr_step_idx in show_step:
                show_message(plan_messages, "Planner")
            response = self.vlm.predict(plan_messages)
            try:
                raw_plan = response.choices[0].message.content
                logger.info("Plan from VLM:\n%s" % raw_plan)
                plan_thought, plan, current_subgoal = self.planner.parse_response(raw_plan)
                logger.info("PLAN THOUGHT: %s" % plan_thought)
                logger.info("PLAN: %s" % plan)
                logger.info("CURRENT SUBGOAL: %s" % current_subgoal)
                step_data.plan = plan
                step_data.sub_goal = current_subgoal
            except Exception as e:
                logger.warning(f"Failed to parse the plan. Error: {e}")

        # Call Operator
        action_thought, action, action_s = None, None, None
        operator_messages = self.operator.get_message(self.episode_data)
        if self.curr_step_idx in show_step:
            show_message(operator_messages, "Operator")
        response = self.vlm.predict(operator_messages, stop=['Summary'])

        for counter in range(self.max_reflection_action):
            try:
                raw_action = response.choices[0].message.content
                logger.info("Action from VLM:\n%s" % raw_action)
                step_data.content = raw_action
                resized_size = (resized_width, resized_height)
                action_thought, action, action_s = self.operator.parse_response(raw_action, resized_size, pixels.size)
                logger.info("ACTION THOUGHT: %s" % action_thought)
                logger.info("ACTION: %s" % str(action))
                break
            except Exception as e:
                logger.warning(f"Failed to parse the action. Error is {e.args}")
                msg = {
                    'type': 'text', 
                    'text': f"Failed to parse the action.\nError is {e.args}\nPlease follow the output format to provide a valid action:"
                }
                operator_messages[-1]['content'].append(msg)
                response = self.vlm.predict(operator_messages, stop=['Summary'])
        if counter > 0:
            operator_messages[-1]['content'] = operator_messages[-1]['content'][:-counter]

        if action is None:
            logger.warning("Action parse error after max retry.")
        else:
            if action.name == 'finished':
                logger.info(f"Finished: {action}")
                self.status = AgentStatus.FINISHED
                answer = action.parameters.get('content', None)
            else:
                logger.info(f"Execute the action: {action}")
                try:
                    self.env.execute_action(action)
                except Exception as e:
                    logger.warning(f"Failed to execute the action: {action}. Error: {e}")
                    action = None
        
        if action is not None:
            step_data.thought = action_thought
            step_data.action_desc = action_thought
            step_data.action_s = action_s
            step_data.action = action

        step_data.exec_env_state = self.env.get_state()

        # Call Reflector
        if self.use_reflector:
            reflection_messages = self.reflector.get_message(self.episode_data)
            reflection_messages = remove_img_placeholder(reflection_messages)
            if self.curr_step_idx in show_step:
                show_message(reflection_messages, "Reflector")
            response = self.vlm.predict(reflection_messages)
            try:
                content = response.choices[0].message.content
                logger.info("Reflection from VLM:\n%s" % content)
                outcome, error_description = self.reflector.parse_response(content)
                if outcome in ['A', 'B', 'C']:
                    logger.info("Outcome: %s" % outcome)
                    logger.info("Error Description: %s" % error_description)
                    step_data.reflection_outcome = outcome
                    step_data.reflection_error = error_description
            except Exception as e:
                logger.warning(f"Failed to parse the reflection. Error: {e}")

        # Call NoteTaker
        if self.use_note_taker:
            note_messages = self.note_taker.get_message(self.episode_data)
            note_messages = remove_img_placeholder(note_messages)
            if self.curr_step_idx in show_step:
                show_message(note_messages, "NoteTaker")
            response = self.vlm.predict(note_messages)
            try:
                content = response.choices[0].message.content
                logger.info("Memory from VLM:\n%s" % content)
                memory = self.note_taker.parse_response(content)
                logger.info("Memory: %s" % memory)
                step_data.memory = memory
            except Exception as e:
                logger.warning(f"Failed to parse the memory. Error: {e}")

        # Call Processor
        if self.use_processor:
            processor_messages = self.processor.get_message(self.episode_data)
            processor_messages = remove_img_placeholder(processor_messages)
            if self.curr_step_idx in show_step:
                show_message(processor_messages, "Processor")
            response = self.vlm.predict(processor_messages)
            try:
                content = response.choices[0].message.content
                logger.info("Progress from VLM:\n%s" % content)
                progress = self.processor.parse_response(content)
                logger.info("Progress: %s" % progress)
                step_data.progress = progress
            except Exception as e:
                logger.warning(f"Failed to parse the progress. Error: {e}")

        if self.status == AgentStatus.FINISHED:
            if answer is None:
                # Answer
                msg = {
                    'type': 'text', 'text': ANSWER_PROMPT_TEMPLATE.format(goal=self.goal)
                }
                operator_messages[-1]['content'].append(msg)
                show_message(operator_messages, "Answer")
                response = self.vlm.predict(operator_messages)
                try:
                    content = response.choices[0].message.content
                    logger.info("Answer from VLM:\n%s" % content)
                    _, answer, _ = self.operator.parse_response(content, resized_size, pixels.size)
                    answer = answer.parameters.get('content', None)
                    step_data.answer = answer
                    logger.info("Answer: %s" % answer)
                except Exception as e:
                    logger.warning(f"Failed to get the answer. Error: {e}")

            # Evolutor
            if self.use_evolutor:
                evolutor_messages = self.evolutor.get_message(self.episode_data)
                evolutor_messages = remove_img_placeholder(evolutor_messages)
                show_message(evolutor_messages, "Evolutor")
                response = self.vlm.predict(evolutor_messages)
                try:
                    content = response.choices[0].message.content
                    logger.info("Updated tips from VLM:\n%s" % content)
                    updated_tips = self.evolutor.parse_response(content)
                    logger.info("Updated tips: %s" % updated_tips)
                    self.episode_data.output_tips = updated_tips
                    self.tips = updated_tips
                except Exception as e:
                    logger.warning(f"Failed to parse the updated tips. Error: {e}")

        return answer


    def iter_run(self, input_content: str, stream: bool=False) -> Iterator[StepData]:
        """Execute the agent with user input content.

        Returns: Iterator[StepData]
        """

        if self.state == AgentState.READY:
            self.reset(goal=input_content)
            logger.info("Start task: %s, with at most %d steps" % (self.goal, self.max_steps))
        elif self.state == AgentState.CALLUSER:
            self._user_input = input_content      # user answer
            self.state = AgentState.RUNNING       # reset agent state
            logger.info("Continue task: %s, with user input %s" % (self.goal, input_content))
        else:
            raise Exception('Error agent state')

        for step_idx in range(self.curr_step_idx, self.max_steps):
            self.curr_step_idx = step_idx
            try:
                self.step()
                yield self._get_curr_step_data()
            except Exception as e:
                self.status = AgentStatus.FAILED
                self.episode_data.status = self.status
                self.episode_data.message = str(e)
                yield self._get_curr_step_data()
                return

            self.episode_data.num_steps = step_idx + 1
            self.episode_data.status = self.status

            if self.status == AgentStatus.FINISHED:
                logger.info("Agent indicates task is done.")
                self.episode_data.message = 'Agent indicates task is done'
                yield self._get_curr_step_data()
                return
            elif self.state == AgentState.CALLUSER:
                logger.info("Agent indicates to ask user for help.")
                yield self._get_curr_step_data()
                return
            else:
                logger.info("Agent indicates one step is done.")
            yield self._get_curr_step_data()
        logger.warning(f"Agent reached max number of steps: {self.max_steps}.")

    def run(self, input_content: str) -> EpisodeData:
        """Execute the agent with user input content.

        Returns: EpisodeData
        """
        for _ in self.iter_run(input_content, stream=False):
            pass
        return self.episode_data
