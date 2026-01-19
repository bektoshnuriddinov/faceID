from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
from insightface.app import FaceAnalysis


# =======================
# Constants
# =======================

EMB_SIZE = 512


# =======================
# Data structures
# =======================

@dataclass
class FaceFound:
    bbox: Tuple[int, int, int, int]   # x1, y1, x2, y2
    det_score: float
    face_size: int
    blur: float
    embedding: List[float]            # 512-d normalized embedding
    face_b64: str                     # cropped face (base64 jpeg)


# =======================
# Utility functions
# =======================

def _blur_score(image_bgr: np.ndarray) -> float:
    """Laplacian-based blur score (higher = sharper)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _clamp_bbox(
    b: Tuple[float, float, float, float],
    w: int,
    h: int
) -> Tuple[int, int, int, int]:
    """Clamp bounding box to image bounds."""
    x1, y1, x2, y2 = map(int, b)
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(0, min(x2, w))
    y2 = max(0, min(y2, h))
    return x1, y1, x2, y2


def _crop_to_base64_jpeg(
    image_bgr: np.ndarray,
    bbox: Tuple[int, int, int, int],
    *,
    quality: int = 85
) -> str:
    """Crop face and return base64-encoded JPEG."""
    import base64

    x1, y1, x2, y2 = bbox
    crop = image_bgr[y1:y2, x1:x2]

    if crop.size == 0:
        crop = image_bgr

    ok, buf = cv2.imencode(
        ".jpg",
        crop,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )

    if not ok:
        ok, buf = cv2.imencode(".jpg", image_bgr)

    return base64.b64encode(buf.tobytes()).decode("ascii")

def add_margin(image, margin_ratio=0.05):
    h, w = image.shape[:2]

    top = int(h * margin_ratio)
    bottom = int(h * margin_ratio)
    left = int(w * margin_ratio)
    right = int(w * margin_ratio)

    color = [255, 255, 255]

    new_img = cv2.copyMakeBorder(
        image,
        top, bottom, left, right,
        borderType=cv2.BORDER_CONSTANT,
        value=color
    )

    return new_img


# =======================
# Face detection pipeline
# =======================

def detect_all_faces_strict(
    image_bgr: np.ndarray,
    face_app: FaceAnalysis,
    *,
    min_det_score: float = 0.60,
    min_face_size: int = 80,
    min_blur: float = 60.0,
    max_faces: int = 10,
) -> List[FaceFound]:
    """
    Detect faces, apply strict quality gates, and return embeddings + cropped faces.

    All parameters after `*` are keyword-only.
    """
    image_bgr = add_margin(image_bgr, margin_ratio=0.05)
    faces = face_app.get(image_bgr)
    if not faces:
        return []

    h, w = image_bgr.shape[:2]
    results: List[FaceFound] = []

    for f in faces:
        det_score = float(getattr(f, "det_score", 0.0))
        bbox = _clamp_bbox(
            getattr(f, "bbox", (0, 0, 0, 0)),
            w,
            h,
        )

        x1, y1, x2, y2 = bbox
        face_w, face_h = (x2 - x1), (y2 - y1)
        face_size = min(face_w, face_h)

        if face_w > 0 and face_h > 0:
            crop = image_bgr[y1:y2, x1:x2]
        else:
            crop = image_bgr

        blur = _blur_score(crop)

        # -----------------------
        # Quality gates
        # -----------------------
        if det_score < min_det_score:
            continue

        if face_size < min_face_size:
            continue

        if blur < min_blur:
            continue

        emb = getattr(f, "normed_embedding", None)
        if emb is None or len(emb) != EMB_SIZE:
            continue

        face_b64 = _crop_to_base64_jpeg(
            image_bgr,
            bbox,
            quality=85,
        )

        results.append(
            FaceFound(
                bbox=bbox,
                det_score=det_score,
                face_size=face_size,
                blur=blur,
                embedding=emb.tolist(),
                face_b64=face_b64,
            )
        )

    # Sort by confidence and size, take top-N
    results.sort(
        key=lambda x: (x.det_score, x.face_size),
        reverse=True,
    )

    return results[:max_faces]
