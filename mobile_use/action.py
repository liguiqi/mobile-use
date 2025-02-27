
import logging

logger = logging.getLogger(__name__)



ACTION_SPACE = {
    "click": {
        "name": "CLICK",
        "description": "Click on the screen at the given position.",
        "parameters": {
            "point": {
                "type": "array",
                "description": "The coordinate point position to click, such as [230, 560]."
            }
        }
    },
    "long_press": {
        "name": "LONG PRESS",
        "description": "Long press on the screen at the given position.",
        "parameters": {
            "point": {
                "type": "array",
                "description": "The coordinate point position to long press, such as [230, 560]."
            }
        }
    },
    "type": {
        "name": "TYPE",
        "description": "Type text on the screen.",
        "parameters": {
            "text": {"type": "str", "description": "The text to type."}
        }
    },
    "scroll": {
        "name": "SCROLL",
        "description": "Scrolls at (x, y) in the given direction.",
        "parameters": {
            "start_point": {
                "type": "array",
                "description": "The coordinate point position to the scroll start point, such as [230, 560]."
            },
            "end_point": {
                "type": "array",
                "description": "The coordinate point position to the scroll end point, such as [230, 560]."
            }
        }
    },
    "press_home": {
        "name": "PRESS HOME",
        "description": "Press the home button."
    },
    "press_back": {
        "name": "PRESS BACK",
        "description": "Press the back button."
    },
    "wait": {
        "name": "WAIT",
        "description": "Wait for a brief moment."
    },
    "finished": {
        "name": "FINISHED",
        "description": "A special flag indicating that the task has been completed",
        "parameters": {
            "answer": {
                "type": "str",
                "description": "The final answer for the task goal."
            }
        }
    },
    "call_user": {
        "name": "ASK HUMAN",
        "description": "Ask human for help."
    }
}
