import os
import unittest
from mobile_use import Agent, Environment, VLMWrapper


class TestAgent(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        self.env = Environment(serial_no='', port=5038, go_home=False)
        self.vlm = VLMWrapper(
            model_name="qwen2.5-vl-72b-instruct", 
            api_key=os.getenv('VLM_API_KEY'),
            base_url=os.getenv('VLM_BASE_URL'),
            max_tokens=128,
            max_retry=1,
            temperature=0.0
        )

    def test_ReAct_agent_step(self):
        self.env.reset()
        agent = Agent.from_params(dict(type='ReAct', env=self.env, vlm=self.vlm, max_steps=1))
        agent.reset(goal='Open the Photos')
        for step_data in agent.step():
            print("Thought:", step_data.thought)
        assert step_data.action is not None

    def test_Qwen_agent_step(self):
        self.env.reset()
        agent = Agent.from_params(dict(type='Qwen', env=self.env, vlm=self.vlm, max_steps=1))
        agent.reset(goal='Open the Photos')
        for step_data in agent.step():
            print("Thought:", step_data.thought)
        assert step_data.action is not None

    def test_QwenWithSummary_agent_dtep(self):
        self.env.reset()
        agent = Agent.from_params(dict(type='QwenWithSummary', env=self.env, vlm=self.vlm, max_steps=1))
        agent.reset(goal='Open the Photos')
        agent.step()
        step_data = agent._get_curr_step_data()
        print("Thought:", step_data.thought)
        assert step_data.action is not None

    def test_MultiAgent_agent_step(self):
        self.env.reset()
        agent = Agent.from_params(dict(type='MultiAgent', env=self.env, vlm=self.vlm, max_steps=1))
        agent.reset(goal='Open the Photos')
        agent.step()
        step_data = agent._get_curr_step_data()
        print("Thought:", step_data.thought)
        assert step_data.action is not None
