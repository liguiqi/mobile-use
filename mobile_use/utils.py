import math
import base64
from io import BytesIO
from PIL import Image
from typing import Tuple, Union, List


def encode_image_url(image: Image.Image, resize: Union[Tuple, List]=None) -> str:
    """Encode an image to base64 string.
    """
    if resize:
        image = image.copy()
        image.thumbnail(resize)
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    base64_url = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{base64_url}"


def contains_chinese(text):
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def smart_resize(
    height: int, width: int, factor: int = 28, min_pixels: int = 4 * 28 * 28, max_pixels: int = 16384 * 28 * 28
) -> tuple[int, int]:
    """
    Implemented by Qwen2.5-VL
    More detail see: https://github.com/QwenLM/Qwen2.5-VL/blob/main/qwen-vl-utils/src/qwen_vl_utils/vision_process.py
    """
    MAX_RATIO = 200
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {MAX_RATIO}, got {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round(height / factor) * factor)
    w_bar = max(factor, round(width / factor) * factor)
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = math.floor(height / beta / factor) * factor
        w_bar = math.floor(width / beta / factor) * factor
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = math.ceil(height * beta / factor) * factor
        w_bar = math.ceil(width * beta / factor) * factor
    return h_bar, w_bar
