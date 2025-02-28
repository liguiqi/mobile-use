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
