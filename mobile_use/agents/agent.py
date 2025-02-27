import logging
import re
from typing import List, Iterator

from mobile_use.scheme import *
from mobile_use.environ import Environment
from mobile_use.vlm import VLMWrapper
from mobile_use.utils import encode_image_url
from mobile_use.agents import Agent
logger = logging.getLogger(__name__)


PROMPT_PREFIX = """
You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task. 

## Output Format
```\nThought: ...
Action: ...\n```

## Action Space
click(point='(x1,y1)')
long_press(point='(x1,y1)')
type(text='')
scroll(start_point='(x1,y1)', end_point='(x3,y3)')
press_home()
press_back()
finished() # Submit the task regardless of whether it succeeds or fails.
call_user(question='') # Submit the task and call the user when the task is unsolvable, or when you need the user's help.

## Note
- Use English in `Thought` part.
- Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.
- Action click, long_press and scroll must contain coordinates within 

## User Instruction
"""

# PROMPT_PREFIX = """
# 你是一个手机自动化操作GUI智能体，完成用户提供的任务指令。你需要结合当前屏幕截图，以及历史的截图与操作，确定下一步需要执行的操作（Action）。

# ## Output Format
# ```\nThought: ...
# Action: ...\n```

# ## Action Space
# - click(point='(x1,y1)'): 点击屏幕指定的坐标点(x1, y1)
# - long_press(point='(x1,y1)'): 长按屏幕指定坐标点(x1, y1)
# - type(text=''): 通过键盘输入文本
# - scroll(start_point='(x1,y1)', end_point='(x2,y2)'): 滚动屏幕，(x1,y1) 为起始坐标位置，(x2,y2) 为结束坐标位置。特别地，当y1=y2时可以实现桌面左右滑动切换页面，这对寻找指定应用非常有帮助。
# - press_home(): 回到主页
# - press_back(): 返回上一页
# - finished(): 任务结束标志， 无论任务成功与否，都需要通过该操作结束.
# - call_user(question=''): 当前需要用户提供更多补充信息时，请用户发起提问

# ## Note
# - 如果没有安装相应的应用，提示用户先安装相应的应用，向用户提问
# - 关于Thought部分内容，根据用户指令，结合历史操作，详细思考你的解决过程，用简要的话术列出下一步操作计划
# - Action操作 click、long_press 和 scroll 必须包含坐标点

# 现在，让我们开始吧！

# 任务指令: 
# """.strip()


def parse_reason_and_action(content: str, size: tuple[float, float], raw_size: tuple[float, float]) -> Action:
    reason = re.search(
        r'Thought:(.*)Action:', content, flags=re.DOTALL
    )
    if reason:
        reason_s = reason.group(1).strip()
    else:
        reason_s = None
    
    action = re.search(
        r'Action:(.*)', content, flags=re.DOTALL
    )

    action_s = action.group(1).strip()
    name = re.search(r'([a-z_]+)', action_s.lower()).group(1).strip()

    params = {}
    action_params = re.findall(r"(\w+)='([^']*)'", action_s)
    if len(action_params):
        for k, v in action_params:
            try:
                x, y = eval(v)
                x = round(x / size[0] * raw_size[0])
                y = round(y / size[1] * raw_size[1])
                params[k] = (x, y)
            except:
                params[k] = v.strip()
    
    action_a = Action(name=name, parameters=params)
    return reason_s, action_a


@Agent.register('default')
class DefaultAgent(Agent):
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

    def _remain_most_recent_images(self):
        couter = 0
        for i in range(len(self.messages)-1, -1, -1):
            message = self.messages[i]
            if isinstance(message['content'], list):
                j = len(message['content']) - 1
                while j >= 0:
                    cnt = message['content'][j]
                    if cnt['type'] == 'image_url':
                        if couter >= self.num_latest_screenshot:
                            message['content'].pop(j)
                        else:
                            couter += 1
                    j -= 1

    def _get_curr_step_data(self) -> StepData:
        if len(self.trajectory) > self.curr_step_idx:
            return self.trajectory[self.curr_step_idx]
        else:
            return None

    def _process_response(self, response, stream) -> Iterator[StepData]:
        step_data = self.trajectory[-1]
        step_data.content = ''
        if stream:
            though_start, though_end = False, False
            for chunk in response:
                # print('chunk: ', chunk)
                delta = chunk.choices[0].delta
                if not delta.content:
                    continue
                step_data.content += delta.content
                content = step_data.content
                # print(content)
                if not though_start and 'Thought:' in content:
                    though_start = True
                    step_data.thought = content.split('Thought:')[-1].strip()
                    yield step_data
                elif though_start and not though_end:
                    if 'Action' in content:
                        though_end = True
                        step_data.thought = content.split('Thought:')[-1].split('Action')[0].strip()
                    else:
                        step_data.thought += delta.content
                    yield step_data
        else:
            step_data.content = response.choices[0].message.content
            step_data.thought = step_data.content.split('Thought:')[-1].split('Action')[0].strip()

        logger.info("Content from VLM:\n%s" % step_data.content)

    def step(self, stream: bool=False) -> Iterator[StepData]:
        """Execute the task with maximum number of steps.

        Returns: StepData
        """
        logger.info("Step %d ... ..." % self.curr_step_idx)

        # Init messages
        if self.curr_step_idx == 0:
            self.messages.append({
                'role': 'user', 
                'content': [{'type': 'text', 'text': PROMPT_PREFIX + self.goal}]
            })

        if self.state == AgentState.CALLUSER:
            # Continue step with user input
            msg = {
                'type': 'text', 
                'text': self._user_input
            }
        else:
            # Get the current environment screen
            env_state = self.env.get_state()
            pixels = env_state.pixels.copy()
            pixels.thumbnail((1024, 1024))
            msg = {
                "type": "image_url",
                "image_url": {"url": encode_image_url(pixels)}
            }
            # Add new step data
            self.trajectory.append(StepData(
                step_idx=self.curr_step_idx,
                curr_env_state=env_state,
                vlm_call_history=[]
            ))

        step_data = self.trajectory[-1]
        self.messages[-1]['content'].append(msg)
        self._remain_most_recent_images()
        response = self.vlm.predict(self.messages, stream=stream)
        for _step_data in self._process_response(response, stream=stream):
            yield _step_data
        counter = self.max_reflection_action
        reason, action = None, None
        while counter > 0:
            try:
                content = step_data.content
                step_data.vlm_call_history.append(VLMCallingData(self.messages, response))
                reason, action = parse_reason_and_action(content, pixels.size, env_state.pixels.size)
                logger.info("REASON: %s" % reason)
                logger.info("ACTION: %s" % str(action))
                msg = {'type': 'text', 'text': content}
                self.messages[0]['content'].append(msg)
                break
            except Exception as e:
                logger.warning(f"Failed to parse the action from: {content}.")
                msg = {
                    'type': 'text', 
                    'text': f"Failed to parse the action from: {content}.Error is {e.args}"
                }
                self.messages[0]['content'].append(msg)
                self._remain_most_recent_images()
                response = self.vlm.predict(self.messages)
                for _step_data in self._process_response(response, stream=stream):
                    yield _step_data
                counter -= 1
        if action is None:
            raise Exception("Action parse error after max retry")

        step_data.action = action
        if not stream:
            step_data.thought = reason
        yield step_data

        if action.name.upper() == 'FINISHED':
            logger.info(f"Finished: {action}")
            self.status = AgentStatus.FINISHED
        elif action.name.upper() == 'CALL_USER':
            logger.info(f"Call for help from user:{action}")
            self.state = AgentState.CALLUSER
        else:
            logger.info(f"Execute the action: {action}")
            self.env.execute_action(action)
            step_data.exec_env_state = self.env.get_state()

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
