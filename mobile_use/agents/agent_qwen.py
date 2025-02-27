import logging
import re
from typing import List, Iterator, Union, Tuple
import traceback
import json

from qwen_vl_utils import smart_resize

# from mobile_use.action import ACTION_SPACE
from mobile_use.scheme import *
from mobile_use.environ import Environment
from mobile_use.vlm import VLMWrapper
from mobile_use.utils import encode_image_url
from mobile_use.agents import Agent


logger = logging.getLogger(__name__)

# Qwen2.5-VL-72B-Instruct preprocessor_config
QWEN_MIN_PIXELS = 3136
QWEN_MAX_PIXELS = 12845056
QWEN_PATCH_SIZE = 14
QWEN_MERGE_SIZE = 2

def _smart_resize(image):
    resized_height, resized_width  = smart_resize(image.height,
        image.width,
        factor=QWEN_PATCH_SIZE * QWEN_MERGE_SIZE,
        min_pixels=QWEN_MIN_PIXELS,
        max_pixels=QWEN_MAX_PIXELS)
    return resized_width, resized_height

# _smart_resize: 1092 2408
# pixels.thumbnail((1024, 1024)): 461 1024

SYSTEM_PROMPT = """
You are a helpful assistant.

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"type": "function", "function": {"name_for_human": "mobile_use", "name": "mobile_use", "description": "Use a touchscreen to interact with a mobile device, and take screenshots.
* This is an interface to a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.
* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions.
* The screen's resolution is 1092x2408.
* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don't click boxes on their edges unless asked.", "parameters": {"properties": {"action": {"description": "The action to perform. The available actions are:
* `key`: Perform a key event on the mobile device.
    - This supports adb's `keyevent` syntax.
    - Examples: "volume_up", "volume_down", "power", "camera", "clear".
* `click`: Click the point on the screen with coordinate (x, y).
* `long_press`: Press the point on the screen with coordinate (x, y) for specified seconds.
* `swipe`: Swipe from the starting point with coordinate (x, y) to the end point with coordinates2 (x2, y2).
* `type`: Input the specified text into the activated input box.
* `answer`: Output the answer.
* `system_button`: Press the system button.
* `open`: Open an app on the device.
* `wait`: Wait specified seconds for the change to happen.
* `terminate`: Terminate the current task and report its completion status.", "enum": ["key", "click", "long_press", "swipe", "type", "answer", "system_button", "open", "wait", "terminate"], "type": "string"}, "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=click`, `action=long_press`, and `action=swipe`.", "type": "array"}, "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=swipe`.", "type": "array"}, "text": {"description": "Required only by `action=key`, `action=type`, `action=answer`, and `action=open`.", "type": "string"}, "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.", "type": "number"}, "button": {"description": "Back means returning to the previous interface, Home means returning to the desktop, Menu means opening the application background menu, and Enter means pressing the enter. Required only by `action=system_button`", "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"}, "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string", "enum": ["success", "failure"]}}, "required": ["action"], "type": "object"}, "args_format": "Format the arguments as a JSON object."}}
</tools>

## Note
- If you think the task is finished, you should terminate the task in time.
- Action click, long_press and swipe must contain coordinates within.
- You may be given some history plan and actions, this is the response from the previous loop.
- You should carefully consider your plan base on the task, screenshot, and history actions.

Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.
For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:

## Format
Thought: The process of thinking.
Action: The next action. Must be one of the Action Space.
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
Summary: Summarize your action.
""".strip()

THINK_AND_SUMMARY_PROMPT = "Before answering, explain your reasoning step-by-step in <thinking></thinking> tags, and insert them before the <tool_call></tool_call> XML tags.\nAfter answering, summarize your action in <conclusion></conclusion> tags, and insert them after the <tool_call></tool_call> XML tags."
IMAGE_PLACEHOLDER = '<|vision_start|><|image_pad|><|vision_end|>'

ACTION_SPACE = ["key", "click", "left_click", "long_press", "swipe", "type", "answer", "system_button", "open", "wait", "terminate"]

@Agent.register('Qwen')
class QwenAgent(Agent):
    def __init__(
            self, 
            env: Environment,
            vlm: VLMWrapper,
            max_steps: int=10,
            num_latest_screenshot: int=10,
            max_reflection_action: int=3,
            reflection_action_waiting_seconds: float=1.0,
            max_retry_vlm: int=3,
            retry_vlm_waiting_seconds: float=1.0,
        ):
        super().__init__(env=env, vlm=vlm, max_steps=max_steps)
        self.num_latest_screenshot = num_latest_screenshot
        self.max_reflection_action = max_reflection_action
        self.reflection_action_waiting_seconds = reflection_action_waiting_seconds
        self.max_retry_vlm = max_retry_vlm
        self.retry_vlm_waiting_seconds = retry_vlm_waiting_seconds

    def reset(self, goal: str='') -> None:
        """Reset the state of the agent.
        """
        self._init_data(goal=goal)

    def _get_curr_step_data(self) -> StepData:
        if len(self.trajectory) > self.curr_step_idx:
            return self.trajectory[self.curr_step_idx]
        else:
            return None

    def _parse_response(self, content: str, size: tuple[float, float], raw_size: tuple[float, float]) -> Action:
        # reason = re.search(r'<thinking>(.*?)</thinking>', content, flags=re.DOTALL)
        reason = re.search(r"Thought:(.*?)(?=\n|Action:|<tool_call>|\{\"name\": \"mobile_use\",)", content, flags=re.DOTALL)
        if reason:
            reason_s = reason.group(1).strip()
        else:
            reason_s = None
        # summary = re.search(r'<conclusion>(.*?)</conclusion>', content, flags=re.DOTALL)
        summary = re.search(r'Summary:(.*?)', content, flags=re.DOTALL)
        if summary:
            summary_s = summary.group(1).strip()
        else:
            summary_s = None
        # action = re.search(r'<tool_call>(.*?)</tool_call>', content, flags=re.DOTALL)
        action = re.search(r'{"name": "mobile_use",(.*?)}}', content, flags=re.DOTALL)
        if not action:
            raise Exception("Cannot extract action in the content.")
        # action_s = action.group(1).strip()
        action_s = '{"name": "mobile_use",' + action.group(1).strip() + '}}'
        action = json.loads(action_s)
        name = action['arguments']['action']
        if name not in ACTION_SPACE:
            raise Exception(f"Action {name} is not in the action space.")
        action['arguments'].pop('action')
        params = action['arguments']

        for k, v in params.items():
            if k in ['coordinate', 'coordinate2', 'point', 'start_point', 'end_point']:
            # if ACTION_SPACE[name].get('parameters', {}).get(k, {}).get('type') == 'array':
                try:
                    x = round(v[0] / size[0] * raw_size[0])
                    y = round(v[1] / size[1] * raw_size[1])
                    params[k] = (x, y)
                except:
                    pass
        action_a = Action(name=name, parameters=params)
        return reason_s, action_a, action_s, summary_s

    def _process_response(self, response, stream) -> Iterator[StepData]:
        step_data = self.trajectory[-1]
        step_data.content = ''
        if stream:
            though_start, though_end = False, False
            for chunk in response:
                pass
                # print('chunk: ', chunk)
                delta = chunk.choices[0].delta
                if not delta.content:
                    continue
                step_data.content += delta.content
                content = step_data.content
                # print(content)
                if not though_start and '<thinking>' in content:
                    though_start = True
                    step_data.thought = content.split('<thinking>')[-1].strip()
                    yield step_data
                elif though_start and not though_end:
                    if '</thinking>' in content:
                        though_end = True
                        step_data.thought = content.split('<thinking>')[-1].split('</thinking>')[0].strip()
                    else:
                        step_data.thought += delta.content
                    yield step_data
        else:
            step_data.content = response.choices[0].message.content

        logger.info("Content from VLM:\n%s" % step_data.content)

    def step(self, stream: bool=False) -> Iterator[StepData]:
        """Execute the task with maximum number of steps.

        Returns: StepData
        """
        logger.info("Step %d ... ..." % self.curr_step_idx)

        # Init messages
        if self.curr_step_idx == 0:
            env_state = self.env.get_state()
            pixels = env_state.pixels.copy()
            # pixels.thumbnail((1024, 1024))
            resized_width, resized_height = _smart_resize(pixels)
            self.messages.append({
                'role': 'system', 
                'content': [
                    {"type": "text", "text": SYSTEM_PROMPT},
                ]
            })
            self.messages.append({
                'role': 'user', 
                'content': [
                    {'type': 'text','text': f'The user query: {self.goal}\nTask progress (You have done the following operation on the current device): None'},
                    {}, # Place holder for observation
                    {}, # Place holder for image
                    # {'type': 'text','text': THINK_AND_SUMMARY_PROMPT},
                ]
            })

            # print("Init messages:")
            # print(self.messages)
            
        user_message_length = len(self.messages[1]['content'])
        if self.state == AgentState.CALLUSER:
            observation = self._user_input
            img_msg = None
        else:
            observation = IMAGE_PLACEHOLDER
            # Get the current environment screen
            env_state = self.env.get_state()
            pixels = env_state.pixels.copy()
            resized_width, resized_height = _smart_resize(pixels)
            # pixels.thumbnail((1024, 1024))
            img_msg = {
                "type": "image_url",
                "min_pixels": QWEN_MIN_PIXELS,
                "max_pixels": QWEN_MAX_PIXELS,
                "image_url": {"url": encode_image_url(pixels)}
            }
            # Add new step data
            self.trajectory.append(StepData(
                step_idx=self.curr_step_idx,
                curr_env_state=env_state,
                vlm_call_history=[]
            ))
        self.messages[-1]['content'][1] = ({
            'type': 'text',
            'text': f'Observation: {observation}'
        })
        if img_msg:
            self.messages[-1]['content'][2] = img_msg
        else:
            # TODO: Keep the most recent image?
            self.messages[-1]['content'][2] = {"type": "text", "text": ""}

        step_data = self.trajectory[-1]
        response = self.vlm.predict(self.messages, stream=stream)
        for _step_data in self._process_response(response, stream=stream):
            yield _step_data
        counter = self.max_reflection_action
        reason, action = None, None
        while counter > 0:
            try:
                content = step_data.content
                step_data.vlm_call_history.append(VLMCallingData(self.messages, response))
                # reason, action, action_s, summary = self._parse_response(content, pixels.size, env_state.pixels.size)
                reason, action, action_s, summary = self._parse_response(content, (resized_width, resized_height), env_state.pixels.size)
                logger.info("REASON: %s" % reason)
                logger.info("ACTION: %s" % str(action))
                logger.info("SUMMARY: %s" % summary)
                break
            except Exception as e:
                logger.warning(f"Failed to parse the action from: {content}.")
                traceback.print_exc()
                msg = {
                    'type': 'text', 
                    'text': f"Failed to parse the action from: {content}.Error is {e.args}\nPlease follow the instruction to provide a valid action."
                }
                self.messages[-1]['content'].append(msg)
                response = self.vlm.predict(self.messages)
                for _step_data in self._process_response(response, stream=stream):
                    yield _step_data
                counter -= 1

        if action is None:
            logger.error("Action parse error after max retry.")
        else:
            if action.name == 'terminate':
                if action.parameters['status'] == 'success':
                    logger.info(f"Finished: {action}")
                    self.status = AgentStatus.FINISHED
                elif action.parameters['status'] == 'failure':
                    logger.info(f"Failed: {action}")
                    self.status = AgentStatus.FAILED
            elif action.name.upper() == 'CALL_USER':
                logger.info(f"Call for help from user:{action}")
                self.state = AgentState.CALLUSER
            else:
                logger.info(f"Execute the action: {action}")

                try:
                    self.env.execute_action(action)
                except Exception as e:
                    logger.error(f"Failed to execute the action: {action}. Error: {e}")
                    traceback.print_exc()
                    action = None
                step_data.exec_env_state = self.env.get_state()

        self.messages[-1]['content'] = self.messages[-1]['content'][:user_message_length]
        if self.curr_step_idx == 0:
            self.messages[-1]['content'][0]['text'] = f'The user query: {self.goal}\nTask progress (You have done the following operation on the current device): '
        
        if action is None:
            self.messages[-1]['content'][0]['text'] += f'\nStep {self.curr_step_idx + 1}: None'
        else:
            # self.messages[-1]['content'][0]['text'] += f'\nStep {self.curr_step_idx + 1}: <thinking>\n{reason}\n</thinking>\n<tool_call>\n{action_s}\n</tool_call>\n<conclusion>\n{summary}\n</conclusion>'
            # self.messages[-1]['content'][0]['text'] += f'\nStep {self.curr_step_idx + 1}: <tool_call>\n{action_s}\n</tool_call> '
            self.messages[-1]['content'][0]['text'] += f'\nStep {self.curr_step_idx + 1}: Thought: {reason}\nAction: \n<tool_call>\n{action_s}\n</tool_call>\nSummary: {summary}'

        step_data.action = action
        if not stream:
            step_data.thought = reason
        yield step_data




    def iter_run(self, input_content: str, stream: bool=True) -> Iterator[StepData]:
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
                for step_data in self.step(stream=stream):
                    yield step_data
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
            elif self.status == AgentStatus.FAILED:
                logger.info("Agent indicates task is failed.")
                self.episode_data.message = 'Agent indicates task is failed'
                yield self._get_curr_step_data()
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
