import cv2
import numpy as np
from insightface.app import FaceAnalysis
from fastapi import HTTPException
from app.utils.response import error


def create_face_app():
    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0)  # ctx_id=0 -> GPU if exists, CPU fallback automatically
    return app


def get_face_embedding(image, face_app: FaceAnalysis):
    faces = face_app.get(image)
    if not faces:
        return None, error(message="Rasmda yuz topilmadi!", person_id=None)
    return faces[0].normed_embedding.tolist(), None
