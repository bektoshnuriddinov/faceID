from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
from insightface.app import FaceAnalysis

EMB_SIZE = 512


@dataclass
class FaceCandidate:
    bbox: Tuple[int, int, int, int]
    det_score: float
    face_size: int
    blur: float

    embedding: List[float] | None
    face_b64: str

    quality_ok: bool
    quality_issues: List[str]


def _blur_score(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _clamp_bbox(b, w, h):
    x1, y1, x2, y2 = map(int, b)
    return (
        max(0, min(x1, w - 1)),
        max(0, min(y1, h - 1)),
        max(0, min(x2, w)),
        max(0, min(y2, h)),
    )


def _crop_to_base64_jpeg(image_bgr, bbox, quality=85) -> str:
    import base64
    x1, y1, x2, y2 = bbox
    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        crop = image_bgr
    ok, buf = cv2.imencode(
        ".jpg",
        crop,
        [int(cv2.IMWRITE_JPEG_QUALITY), quality],
    )
    if not ok:
        ok, buf = cv2.imencode(".jpg", image_bgr)
    return base64.b64encode(buf.tobytes()).decode("ascii")


def add_margin(image, ratio=0.05):
    h, w = image.shape[:2]
    m = int(min(h, w) * ratio)
    return cv2.copyMakeBorder(
        image, m, m, m, m,
        cv2.BORDER_CONSTANT,
        value=[255, 255, 255],
    )


def detect_all_faces_with_quality(
    image_bgr: np.ndarray,
    face_app: FaceAnalysis,
    *,
    min_det_score: float = 0.60,
    min_face_size: int = 80,
    min_blur: float = 60.0,
    max_faces: int = 10,
) -> List[FaceCandidate]:

    image_bgr = add_margin(image_bgr)
    faces = face_app.get(image_bgr)
    if not faces:
        return []

    h, w = image_bgr.shape[:2]
    results: List[FaceCandidate] = []

    for f in faces:
        issues: List[str] = []

        det_score = float(getattr(f, "det_score", 0.0))
        bbox = _clamp_bbox(
            getattr(f, "bbox", (0, 0, 0, 0)),
            w,
            h,
        )

        x1, y1, x2, y2 = bbox
        face_size = min(x2 - x1, y2 - y1)

        crop = image_bgr[y1:y2, x1:x2] if face_size > 0 else image_bgr
        blur = _blur_score(crop)

        # -------- QUALITY CHECK (SOFT) --------
        if det_score < min_det_score:
            issues.append("low_detection_score")
        if face_size < min_face_size:
            issues.append("face_too_small")
        if blur < min_blur:
            issues.append("image_blurry")

        emb = getattr(f, "normed_embedding", None)
        if emb is None or len(emb) != EMB_SIZE:
            issues.append("embedding_not_available")
            embedding = None
        else:
            embedding = emb.tolist()

        results.append(
            FaceCandidate(
                bbox=bbox,
                det_score=det_score,
                face_size=face_size,
                blur=blur,
                embedding=embedding,
                face_b64=_crop_to_base64_jpeg(image_bgr, bbox),
                quality_ok=(len(issues) == 0),
                quality_issues=issues,
            )
        )
    results.sort(
        key=lambda x: (x.quality_ok, x.det_score, x.face_size),
        reverse=True,
    )

    return results[:max_faces]
