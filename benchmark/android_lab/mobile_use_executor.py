import time
import logging
from PIL import Image
from mobile_use.scheme import Action
from mobile_use.environ import Environment, EnvState
from page_executor.text_executor import TextOnlyExecutor
from utils_mobile.and_controller import AndroidController
from evaluation.evaluation import print_with_color


logger = logging.getLogger(__name__)


class MobileUseExecutor(TextOnlyExecutor):

    def __call__(self, code_snippet):
        '''
        self.new_page_captured = False
        self.controller.on("page", self.__capture_new_page__)
        self.current_return = None'''

        current_return = self.current_return
        local_context = self.__get_class_methods__()
        local_context.update(**{'self': self})
        return current_return
    
    def execute_action(self, action: Action):
        print_with_color(f"Execute Action {action}", "green")
        answer = None
        if action.name == 'open_app':
            package_name = action.parameters['package_name']
            self.controller.launch(package_name)
            self.current_return = {"operation": "do", "action": 'Launch', "kwargs": {"package": package_name}}
        elif action.name == 'open':
            raise Exception('open action is unavailable, please use open_app')
        elif action.name == 'click' or action.name == 'left_click':
            if 'coordinate' in action.parameters:       # QwenAgent
                x, y = action.parameters['coordinate']
            elif 'start_box' in action.parameters:
                x, y = action.parameters['start_box']
            else:
                x, y = action.parameters['point']
            self.controller.tap(x, y)
            self.current_return = {"operation": "do", "action": 'Tap', "kwargs": {"element": [x, y]}}
        elif action.name == 'long_press':
            if 'coordinate' in action.parameters:       # QwenAgent
                x, y = action.parameters['coordinate']
            elif 'start_box' in action.parameters:
                x, y = action.parameters['start_box']
            else:
                x, y = action.parameters['point']
            # duration = action.parameters.get('time', 2.0)
            self.controller.long_press(x, y)
            self.current_return = {"operation": "do", "action": 'Long Press', "kwargs": {"element": [x, y]}}
        elif action.name == 'type':
            if 'content' in action.parameters:
                text = action.parameters['content']
            else:
                text = action.parameters['text']
            self.controller.text(text)
            self.current_return = {"operation": "do", "action": 'Type', "kwargs": {"text": text}}
        elif action.name == 'key':
            text = action.parameters['text']
            self.controller.execute_adb(f'adb shell input keyevent {text}', type=self.controller.type)
            self.current_return = {"operation": "do", "action": f'Press {text}'}
        elif action.name == 'scroll':
            if 'start_box' in action.parameters:
                x1, y1 = action.parameters['start_box']
                x2, y2 = action.parameters['end_box']
            else:
                x1, y1 = action.parameters['start_point']
                x2, y2 = action.parameters['end_point']
            self.controller.execute_adb(f'adb shell input swipe {x1}, {y1}, {x2}, {y2} 500', type=self.controller.type)
            self.current_return = {"operation": "do", "action": 'Swipe', "kwargs": {"element": [x1, y1], "direction": '', "dist": 'medium'}}
        elif action.name == 'swipe':       # QwenAgent
            x1, y1 = action.parameters['coordinate']
            x2, y2 = action.parameters['coordinate2']
            self.controller.execute_adb(f'adb shell input swipe {x1}, {y1}, {x2}, {y2} 500', type=self.controller.type)
            self.current_return = {"operation": "do", "action": 'Swipe', "kwargs": {"element": [x1, y1], "direction": '', "dist": 'medium'}}
        elif action.name == 'press_home':
            self.controller.home()
            self.current_return = {"operation": "do", "action": 'Press Home'}
        elif action.name == 'press_back':
            self.controller.back()
            self.current_return = {"operation": "do", "action": 'Press Back'}
        elif action.name == 'wait':
            duration = action.parameters.get('time', 5.0)
            time.sleep(duration)
        elif action.name == 'answer':
            answer = action.parameters['text']
            self.controller.execute_adb(
                f'adb shell am broadcast com.example.ACTION_UPDATE_OVERLAY --es task_type_string "Agent answered:" --es goal_string "{answer}"',
                type=self.controller.type)
        elif action.name == 'system_button':
            button = action.parameters['button']
            if button == 'Back':
                self.controller.back()
                self.current_return = {"operation": "do", "action": 'Press Back'}
            elif button == 'Home':
                self.controller.home()
                self.current_return = {"operation": "do", "action": 'Press Home'}
            elif button == 'Menu':
                self.controller.execute_adb(f'adb shell input keyevent Menu', type=self.controller.type)
                self.current_return = {"operation": "do", "action": 'Press Menu'}
            elif button == 'Enter':
                self.controller.enter()
                self.current_return = {"operation": "do", "action": 'Press Enter'}
        elif action.name == 'clear_text':
            self.controller.execute_adb(f'adb shell ime enable com.android.adbkeyboard/.AdbIME', type=self.controller.type)
            logger.info(re)
            self.controller.execute_adb(f'adb shell ime set com.android.adbkeyboard/.AdbIME', type=self.controller.type)
            logger.info(re)
            time.sleep(1)
            self.controller.execute_adb(f'adb shell am broadcast -a ADB_CLEAR_TEXT', type=self.controller.type)
            re = self.controller.execute_adb(
                f'adb shell ime disable com.android.adbkeyboard/.AdbIME',
                type=self.controller.type)
            logger.info(re)
            re = self.controller.execute_adb(f'adb shell input text ', type=self.controller.type)
            logger.info(re)
            self.current_return = {"operation": "do", "action": 'Clear text'}
        elif action.name == 'take_note':
            note = action.parameters['text']
            return note
        else:
            raise ValueError(f"Unknown action: {action.name}")
        time.sleep(2)       # wait action ready
        return answer


class AndroidLabEnvironment(Environment):
    def __init__(self, controller: AndroidController, config, page_executor: MobileUseExecutor):
        self.config = config
        self.controller = controller
        self.executor = page_executor

    def reset(self, go_home: bool = False):
        if go_home:
            self.controller.home()

    def get_state(self):
        if self.executor.current_screenshot is None:
            self.executor.update_screenshot()
        try:
            pixels = Image.open(self.executor.current_screenshot)
        except Exception as e:
            logger.error(f"Failed to get screenshot: {e}.")
            raise(e)
        state = EnvState(pixels=pixels, package='')
        return state

    def get_time(self) -> str:
        re = self.controller.execute_adb('adb shell date', type=self.controller.type)
        return re
    
    def execute_action(self, action):
        return self.executor.execute_action(action=action)

    # def execute_action(self, action: Action):
    #     print_with_color(f"Execute Action {action}", "green")
    #     answer = None
    #     if action.name == 'open_app':
    #         package_name = action.parameters['package_name']
    #         self.controller.launch(package_name)
    #     elif action.name == 'open':
    #         raise Exception('open action is unavailable, please use open_app')
    #     elif action.name == 'click' or action.name == 'left_click':
    #         if 'coordinate' in action.parameters:       # QwenAgent
    #             x, y = action.parameters['coordinate']
    #         elif 'start_box' in action.parameters:
    #             x, y = action.parameters['start_box']
    #         else:
    #             x, y = action.parameters['point']
    #         self.controller.tap(x, y)
    #     elif action.name == 'long_press':
    #         if 'coordinate' in action.parameters:       # QwenAgent
    #             x, y = action.parameters['coordinate']
    #         elif 'start_box' in action.parameters:
    #             x, y = action.parameters['start_box']
    #         else:
    #             x, y = action.parameters['point']
    #         # duration = action.parameters.get('time', 2.0)
    #         self.controller.long_press(x, y)
    #     elif action.name == 'type':
    #         if 'content' in action.parameters:
    #             text = action.parameters['content']
    #         else:
    #             text = action.parameters['text']
    #         self.controller.text(text)
    #     elif action.name == 'key':
    #         text = action.parameters['text']
    #         self.controller.execute_adb(f'adb shell input keyevent {text}', type=self.controller.type)
    #     elif action.name == 'scroll':
    #         if 'start_box' in action.parameters:
    #             x1, y1 = action.parameters['start_box']
    #             x2, y2 = action.parameters['end_box']
    #         else:
    #             x1, y1 = action.parameters['start_point']
    #             x2, y2 = action.parameters['end_point']
    #         self.controller.execute_adb(f'adb shell input swipe {x1}, {y1}, {x2}, {y2} 500', type=self.controller.type)
    #     elif action.name == 'swipe':       # QwenAgent
    #         x1, y1 = action.parameters['coordinate']
    #         x2, y2 = action.parameters['coordinate2']
    #         self.controller.execute_adb(f'adb shell input swipe {x1}, {y1}, {x2}, {y2} 500', type=self.controller.type)
    #     elif action.name == 'press_home':
    #         self.controller.home()
    #     elif action.name == 'press_back':
    #         self.controller.back()
    #     elif action.name == 'wait':
    #         duration = action.parameters.get('time', 5.0)
    #         time.sleep(duration)
    #     elif action.name == 'answer':
    #         answer = action.parameters['text']
    #         self.controller.execute_adb(
    #             f'adb shell am broadcast com.example.ACTION_UPDATE_OVERLAY --es task_type_string "Agent answered:" --es goal_string "{answer}"',
    #             type=self.controller.type)
    #     elif action.name == 'system_button':
    #         button = action.parameters['button']
    #         if button == 'Back':
    #             self.controller.back()
    #         elif button == 'Home':
    #             self.controller.home()
    #         elif button == 'Menu':
    #             self.controller.execute_adb(f'adb shell input keyevent Menu', type=self.controller.type)
    #         elif button == 'Enter':
    #             self.controller.enter()
    #     elif action.name == 'clear_text':
    #         self.controller.execute_adb(f'adb shell ime enable com.android.adbkeyboard/.AdbIME', type=self.controller.type)
    #         logger.info(re)
    #         self.controller.execute_adb(f'adb shell ime set com.android.adbkeyboard/.AdbIME', type=self.controller.type)
    #         logger.info(re)
    #         time.sleep(1)
    #         self.controller.execute_adb(f'adb shell am broadcast -a ADB_CLEAR_TEXT', type=self.controller.type)
    #         re = self.controller.execute_adb(
    #             f'adb shell ime disable com.android.adbkeyboard/.AdbIME',
    #             type=self.controller.type)
    #         logger.info(re)
    #         re = self.controller.execute_adb(f'adb shell input text ', type=self.controller.type)
    #         logger.info(re)
    #     elif action.name == 'take_note':
    #         note = action.parameters['text']
    #         return note
    #     else:
    #         raise ValueError(f"Unknown action: {action.name}")
    #     return answer
