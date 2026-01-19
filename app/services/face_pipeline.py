from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple, Any

import cv2
import numpy as np
from insightface.app import FaceAnalysis

EMB_SIZE = 512

@dataclass
class FaceMeta:
    det_score: float
    bbox: Tuple[int, int, int, int]
    face_size: int
    blur: float
    faces_found: int

@dataclass
class FaceEmbeddingResult:
    embedding: List[float]
    meta: FaceMeta

def _blur_score(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def _bbox_area(b: Tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = b
    return max(0, x2 - x1) * max(0, y2 - y1)

def _clamp_bbox(b: Tuple[int, int, int, int], w: int, h: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = b
    x1 = max(0, min(int(x1), w - 1))
    y1 = max(0, min(int(y1), h - 1))
    x2 = max(0, min(int(x2), w))
    y2 = max(0, min(int(y2), h))
    return (x1, y1, x2, y2)

def _select_best_face(faces: list[Any], image_shape) -> Optional[tuple[Any, Tuple[int,int,int,int], float, int]]:
    """
    Выбираем лучшее лицо:
      1) max det_score
      2) при равенстве — max bbox area
    """
    h, w = image_shape[:2]
    best = None
    best_key = None

    for f in faces:
        score = float(getattr(f, "det_score", 0.0))
        bbox_raw = tuple(map(int, f.bbox))  # x1,y1,x2,y2
        bbox = _clamp_bbox(bbox_raw, w, h)
        area = _bbox_area(bbox)
        key = (score, area)

        if best is None or key > best_key:
            best = (f, bbox, score, area)
            best_key = key

    return best
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

def get_face_embedding_strict(
    image_bgr: np.ndarray,
    face_app: FaceAnalysis,
    *,
    min_det_score: float = 0.40,
    min_face_size: int = 80,
    min_blur: float = 60.0,
) -> Optional[FaceEmbeddingResult]:
    """
    Возвращает embedding + meta только если проходит quality gates.
    Иначе возвращает None.
    """
    image_bgr = add_margin(image_bgr, margin_ratio=0.05)
    faces = face_app.get(image_bgr)
    if not faces:
        return None

    picked = _select_best_face(faces, image_bgr.shape)
    if not picked:
        return None

    face, bbox, det_score, _ = picked
    x1, y1, x2, y2 = bbox
    face_w, face_h = (x2 - x1), (y2 - y1)
    face_size = min(face_w, face_h)

    # blur по crop лица (лучше, чем по всему кадру)
    crop = image_bgr[y1:y2, x1:x2] if face_w > 0 and face_h > 0 else image_bgr
    bl = _blur_score(crop)

    # gates
    if det_score < min_det_score:
        return None
    if face_size < min_face_size:
        return None
    if bl < min_blur:
        return None

    emb = getattr(face, "normed_embedding", None)
    if emb is None or len(emb) != EMB_SIZE:
        return None

    meta = FaceMeta(
        det_score=det_score,
        bbox=bbox,
        face_size=face_size,
        blur=bl,
        faces_found=len(faces),
    )
    return FaceEmbeddingResult(embedding=emb.tolist(), meta=meta)
