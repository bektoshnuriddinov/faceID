import cv2
import numpy as np
from insightface.app import FaceAnalysis
from fastapi import Request,HTTPException


def create_face_app(providers=["CUDAExecutionProvider", "CPUExecutionProvider"]):
    app = FaceAnalysis(
    name='buffalo_l',
    providers=providers,
    provider_options={
            "CUDAExecutionProvider": {
                "arena_extend_strategy": "kSameAsRequested"
            }
        }
    )
    app.prepare(ctx_id=0)
    return app

def get_face_embedding(image, face_app: FaceAnalysis):
    faces = face_app.get(image)
    if len(faces) == 0:
        raise HTTPException(status_code=200, detail="Rasmda yuz topilmadi!")
    return faces[0].normed_embedding.tolist()