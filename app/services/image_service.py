from __future__ import annotations
import base64, binascii, os, asyncio
import cv2
import numpy as np

EMB_SIZE = 512

class ImageError(ValueError): ...

def _strip_data_url(b64: str) -> str:
    return b64.split("base64,", 1)[1] if "base64," in b64 else b64

def decode_base64(photo_b64: str) -> bytes:
    try:
        return base64.b64decode(_strip_data_url(photo_b64).strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ImageError("Invalid base64 image") from e

def decode_cv2(img_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ImageError("Invalid image data")
    return img

async def save_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    await asyncio.to_thread(lambda: open(path, "wb").write(data))

def zero_embedding() -> list[float]:
    return [0.0] * EMB_SIZE
