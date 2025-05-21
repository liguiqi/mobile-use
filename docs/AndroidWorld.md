# Deplying MobileUse in AndroidWorld

## Step 1: Environment Setup

Install AndroidWorld by following the guidance in [android_world](https://github.com/google-research/android_world).

Start AndroidWorldAvd and install [ADBKeyboard](https://github.com/senzhk/ADBKeyBoard) in this avd to support special text commands.
```
adb install <path-to-ADBKeyboard.apk>
```

Install mobile-use by following the guidance in [README.md](../README.md).

We recommand you to install mobile-use in the same environment created for AndroidWorld.

📌 **Note**: To run AndroidWorld on the Windows platform, you should use python>=3.12.

## Step 2: Create MobileUse agent in AndroidWorld

Create a new file named `mobile_use_agent.py` in `android_world/android_world/agents` with the following code:
```
"""MobileUse agent for AndroidWorld."""
import logging
import traceback

from android_world.agents import base_agent
from android_world.env import interface
import mobile_use

logger = logging.getLogger(__name__)


class MobileUse(base_agent.EnvironmentInteractingAgent):
  def __init__(
          self, 
          env: interface.AsyncEnv,
          agent: mobile_use.Agent,
          name: str = "MobileUse",
      ):
    super().__init__(env, name)
    self.agent = agent
    self.agent.reset()

  def reset(self, go_home: bool = False) -> None:
    super().reset(go_home)
    self.env.hide_automation_ui()
    self.agent.reset()

  def step(self, goal: str) -> base_agent.AgentInteractionResult:
    if self.agent.goal != goal:
      self.agent.reset(goal=goal)

    answer = None
    try:
      answer = self.agent.step()
    except Exception as e:
      logger.info("Some error happened during the MobileUse agent run.")
      traceback.print_exc()
      self.agent.status = mobile_use.AgentStatus.FAILED
      self.agent.episode_data.status = self.agent.status
      self.agent.episode_data.message = str(e)
      return base_agent.AgentInteractionResult(True, {"step_data": self.agent.trajectory[-1]})

    self.agent.episode_data.num_steps = self.agent.curr_step_idx + 1
    self.agent.episode_data.status = self.agent.status

    if answer is not None:
       logger.info("Agent interaction cache is updated: %s" % answer)
       self.env.interaction_cache = answer

    if self.agent.status == mobile_use.AgentStatus.FINISHED:
        logger.info("Agent indicates task is done.")
        self.agent.episode_data.message = 'Agent indicates task is done.'
        return base_agent.AgentInteractionResult(True, {"step_data": self.agent.trajectory[-1]})
    elif self.agent.state == mobile_use.AgentState.CALLUSER:
        logger.warning("CALLUSER is not supported in AdroidWorld evaluation.")
        return base_agent.AgentInteractionResult(True, {"step_data": self.agent.trajectory[-1]})
    else:
        self.agent.curr_step_idx += 1
        logger.info("Agent indicates one step is done.")
        return base_agent.AgentInteractionResult(False, {"step_data": self.agent.trajectory[-1]})
```

## Step 3: Modify AndroidWorld `run.py`
Import moible-use and the new MobileUse agent created for AndroidWorld:
```
import mobile_use
from android_world.agents import mobile_use_agent
```

Add a new agent option `mobile_use` in function `_get_agent`:
```
def _get_agent(
    env: interface.AsyncEnv,
    family: str | None = None,
) -> base_agent.EnvironmentInteractingAgent:

...

  elif _AGENT_NAME.value == 'mobile_use':
    # Modify the parameters if needed.
    mobile_use_env = mobile_use.Environment(
      serial_no='emulator-5554', 
      port=5037
    )
    mobile_use_vlm = mobile_use.VLMWrapper(
        model_name="qwen2.5-vl-72b-instruct", 
        api_key=os.getenv('VLM_API_KEY'),
        base_url=os.getenv('VLM_BASE_URL'),
    )
    agent = mobile_use.Agent.from_params(dict(
      type='MultiAgent',
      env=mobile_use_env, 
      vlm=mobile_use_vlm, 
    ))
    agent = mobile_use_agent.MobileUse(env, agent)
...
```

## Step 4: Run the AndroidWorld benchmark
Set environment variables for LLM calls.
```
export OPENAI_API_KEY=EMPTY # required by AndroidWorld, useless if you choose MobileUse as your agent
# set the Base URL and API Key of the multimodal large language model for MobileUse
export VLM_API_KEY=<your-api-key>
export VLM_BASE_URL=<your-api-base-url>
```

Run the AndroidWorld benchmark with MobileUse:
```
cd android_world
python run.py --agent_name=mobile_use ...
```
See [android_world: Run the benchmark](https://github.com/google-research/android_world?tab=readme-ov-file#run-the-benchmark) for more details about the AndroidWorld benchmark running.

## Step 5: Best Practice
To achieve great performance on AndroidWorld with MobileUse, you can refer to the following configs:
```
import mobile_use

mobile_use_vlm = mobile_use.VLMWrapper(
    model_name="qwen2.5-vl-72b-instruct",
    api_key=os.getenv('VLM_API_KEY'),
    base_url=os.getenv('VLM_BASE_URL'),
    max_tokens=1024
)

agent = mobile_use.Agent.from_params(dict(
  type='MultiAgent',
  env=mobile_use_env,
  vlm=mobile_use_vlm,
  use_planner=False,
  use_reflector=True,
  use_note_taker=False,
  use_processor=True,
))
```

## Frequent Questions
**Q1: My default adb port 5037 is not available. How to specify another adb port, such as 5038?**

When creating the Mobile Use environment, change the port number:
```
import mobile_use
mobile_use_env = mobile_use.Environment(serial_no=..., port=5038)
```

Specify the port number in AndroidWorld `android_world/android_world/env/android_world_controller.py`:
```
def get_controller(
...
          adb_controller=config_classes.AdbControllerConfig(adb_path=adb_path, adb_server_port=5038),
...
```

Set the environment variable `ANDROID_ADB_SERVER_PORT` before starting the Android Virtual Device.
```
export ANDROID_ADB_SERVER_PORT=5038 # unix platform
# set ANDROID_ADB_SERVER_PORT=5038 ## windows platform
adb start-server
.../emulator -avd AndroidWorldAvd -no-snapshot -grpc 8554
```

**Q2: How to run AndroidWorld on the Windows platform?**

Python >= 3.12 is required.

In `androidworld/run.py` and `androidworld/minimal_task_runner.py`, add your adb path to `_find_adb_directory()`:
```
potential_paths = [r'...\adb.exe']
```

