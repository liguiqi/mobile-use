import logging
import re
from typing import Iterator
import json

from mobile_use.scheme import *
from mobile_use.environ import Environment
from mobile_use.vlm import VLMWrapper
from mobile_use.utils import encode_image_url, smart_resize
from mobile_use.agents import Agent

from mobile_use.agents.sub_agent import Planner, Operator, Reflector, ReflectorWithMemory, NoteTaker, Processor


logger = logging.getLogger(__name__)


ANSWER_PROMPT_TEMPLATE = """
The (overall) user query is: {goal}
Now you have finished the task. I want you to provide an answer to the user query.
Answer with the following format:

## Format
<tool_call>
{{"name": "mobile_use", "arguments": {{"action": "answer", "text": <your-answer>}}}}
</tool_call>"""

def show_message(messages: List[dict], name: str = None):
    name = f"{name} " if name is not None else ""
    logger.info(f"==============={name}MESSAGE==============")
    for message in messages:
        logger.info(f"ROLE: {message['role']}")
        for content in message['content']:
            if content['type'] == 'text':
                logger.info(f"TEXT:")
                logger.info(content['text'])
    logger.info(f"==============={name}MESSAGE END==============")

@Agent.register('MultiAgent')
class MultiAgent(Agent):
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
            use_reflector_with_memory: bool=False,
            use_note_taker: bool=False,
            use_processor: bool=False,
        ):
        super().__init__(env=env, vlm=vlm, max_steps=max_steps)
        self.num_latest_screenshot = num_latest_screenshot
        self.num_histories = num_histories
        self.max_reflection_action = max_reflection_action
        self.reflection_action_waiting_seconds = reflection_action_waiting_seconds
        self.max_retry_vlm = max_retry_vlm
        self.retry_vlm_waiting_seconds = retry_vlm_waiting_seconds

        self.use_planner = use_planner
        self.use_reflector = use_reflector
        self.use_reflector_with_memory = use_reflector_with_memory
        self.use_note_taker = use_note_taker
        self.use_processor = use_processor

        self.planner = Planner()
        self.operator = Operator()
        self.reflector = Reflector()
        self.reflector_with_memory = ReflectorWithMemory()
        self.note_taker = NoteTaker()
        self.processor = Processor()

    def reset(self, goal: str='') -> None:
        """Reset the state of the agent.
        """
        self._init_data(goal=goal)
        self.planner = Planner()
        self.operator = Operator()
        self.reflector = Reflector()
        self.reflector_with_memory = ReflectorWithMemory()
        self.note_taker = NoteTaker()
        self.processor = Processor()

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
        answer = None
        show_step = [0,3]

        # Get the current environment screen
        env_state = self.env.get_state()
        pixels = env_state.pixels
        resized_height, resized_width = smart_resize(height=pixels.height, width=pixels.width)

        # Add new step data
        self.trajectory.append(StepData(
            step_idx=self.curr_step_idx,
            curr_env_state=env_state,
            vlm_call_history=[]
        ))
        step_data = self.trajectory[-1]

        # Call planner
        if self.use_planner:
            plan_messages = self.planner.get_message(self.episode_data)
            if self.curr_step_idx in show_step:
                show_message(plan_messages, "Planner")
            response = self.vlm.predict(plan_messages)
            try:
                raw_plan = response.choices[0].message.content
                logger.info("Plan from VLM:\n%s" % raw_plan)
                plan_thought, plan, current_subgoal = self.planner.parse_response(raw_plan)
                logger.info("PLAN THOUGHT: %s" % plan_thought)
                logger.info("PLAN: %s" % plan)
                step_data.plan = plan
                step_data.sub_goal = current_subgoal
            except Exception as e:
                logger.warning(f"Failed to parse the plan. Error: {e}")

        # Call Operator
        action_thought, action, action_s, action_desc = None, None, None, None
        operator_messages = self.operator.get_message(self.episode_data)
        if self.curr_step_idx in show_step:
            show_message(operator_messages, "Operator")
        response = self.vlm.predict(operator_messages, stop=['Summary'])

        reason, action = None, None
        for counter in range(self.max_reflection_action):
            try:
                raw_action = response.choices[0].message.content
                logger.info("Action from VLM:\n%s" % raw_action)
                step_data.content = raw_action
                resized_size = (resized_width, resized_height)
                action_thought, action, action_s, action_desc = self.operator.parse_response(raw_action, resized_size, pixels.size)
                logger.info("ACTION THOUGHT: %s" % action_thought)
                logger.info("ACTION: %s" % str(action))
                logger.info("ACTION DESCRIPTION: %s" % action_desc)
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
            if action.name == 'terminate':
                if action.parameters['status'] == 'success':
                    logger.info(f"Finished: {action}")
                    self.status = AgentStatus.FINISHED
                elif action.parameters['status'] == 'failure':
                    logger.info(f"Failed: {action}")
                    self.status = AgentStatus.FAILED
            else:
                logger.info(f"Execute the action: {action}")
                try:
                    self.env.execute_action(action)
                except Exception as e:
                    logger.warning(f"Failed to execute the action: {action}. Error: {e}")
                    action = None
        
        if action is not None:
            step_data.thought = action_thought
            step_data.action_desc = action_desc
            step_data.action_s = action_s
            step_data.action = action

        step_data.exec_env_state = self.env.get_state()

        # Call Reflector
        if self.use_reflector:
            reflection_messages = self.reflector.get_message(self.episode_data)
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
                    step_data.reflaction_outcome = outcome
                    step_data.reflaction_error = error_description
            except Exception as e:
                logger.warning(f"Failed to parse the reflection. Error: {e}")

        # Call NoteTaker
        if self.use_note_taker:
            note_messages = self.note_taker.get_message(self.episode_data)
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

        # Answer
        if self.status == AgentStatus.FINISHED:
            msg = {
                'type': 'text', 'text': ANSWER_PROMPT_TEMPLATE.format(goal=self.goal)
            }
            operator_messages[-1]['content'].append(msg)
            if self.curr_step_idx in show_step:
                show_message(operator_messages, "Answer")
            response = self.vlm.predict(operator_messages)
            try:
                content = response.choices[0].message.content
                logger.info("Answer from VLM:\n%s" % content)
                _, answer, _, _ = self.operator.parse_response(content, resized_size, pixels.size)
                answer = answer.parameters['text']
                step_data.answer = answer
                logger.info("Answer: %s" % answer)
            except Exception as e:
                logger.warning(f"Failed to get the answer. Error: {e}")

        return answer


    def iter_run(self, input_content: str) -> Iterator[StepData]:
        pass

    def run(self, input_content: str) -> EpisodeData:
        pass
