import os
import unittest
from mobile_use.scheme import Action, EnvState
from mobile_use.environ import Environment


class TestEnvironment(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        self.env = Environment(serial_no='', port=5038, go_home=False)
    
    def test_get_state(self):
        state = self.env.get_state()
        assert isinstance(state, EnvState)
        assert state.pixels is not None and state.package is not None
    
    def test_execute_action(self):
        action = Action(name='click', parameters={'point': [123, 123]})
        self.env.execute_action(action)

    def test_execute_action_type(self):
        action = Action(name='type', parameters={'text': 'hello world'})
        self.env.execute_action(action)
