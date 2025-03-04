import os
import unittest
from mobile_use.vlm import VLMWrapper


class TestVLMWrapper(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        self.llm = VLMWrapper(
            base_url=os.getenv('VLM_BASE_URL'),
            api_key=os.getenv('VLM_API_KEY'),
            model_name='qwen2.5-vl-72b-instruct'
        )

    def test_predict(self):
        messages = [
            {
                'role': 'user', 
                'content': [{'type': 'text', 'text': 'who are you?'}]
            }
        ]
        response = self.llm.predict(messages, stream=False)
        content = response.choices[0].message.content
        print(content)

    def test_predict_stream(self):
        messages = [
            {
                'role': 'user', 
                'content': [{'type': 'text', 'text': 'who are you?'}]
            }
        ]
        response = self.llm.predict(messages, stream=True)
        for chunk in response:
            delta = chunk.choices[0].delta
            print('chunk delta: ', delta)
