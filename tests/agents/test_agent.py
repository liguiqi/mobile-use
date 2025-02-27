import os
import unittest
from mobile_use import Agent, Environment, VLMWrapper


class TestDefaultAgent(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        env = Environment(port=5038)
        vlm = VLMWrapper(
            model_name="qwen2.5-vl-72b-instruct", 
            api_key=os.getenv('VLM_API_KEY'),
            base_url=os.getenv('VLM_BASE_URL'),
            max_tokens=128,
            max_retry=1,
            temperature=0.0
        )
        self.agent = Agent.from_params(dict(type='default', env=env, vlm=vlm, max_steps=1))

    def test_step(self):
        self.agent.reset(goal='Open the Photos')
        for step_data in self.agent.step():
            print(step_data.thought)
        assert step_data.action is not None
