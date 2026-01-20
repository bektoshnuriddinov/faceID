# app/services/provider_ingest_service.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.repositories.faceid_repo import FaceIdRepo
from app.services.utils import new_uuid
from app.services.image_service import decode_base64, decode_cv2, save_bytes, zero_embedding, ImageError
from app.services.face_pipeline import get_face_embedding_strict
import asyncio

EMB_OK = 1
EMB_NONE = 0
EMB_LOW_QUALITY = 2

@dataclass
class PhotoResult:
    face_url: Optional[str]
    polygons: list[float]
    embedding_status: int
    det_score: float = 0.0
    blur: float = 0.0
    face_size: int = 0
    faces_found: int = 0

def quality_score(p: PhotoResult) -> float:
    """
    Простой скоринг качества:
    - det_score самый важный
    - blur и face_size дают бонус
    """
    return (p.det_score * 100.0) + (min(p.blur, 300.0) * 0.2) + (min(p.face_size, 200) * 0.5)

class ProviderIngestService:
    def __init__(self, repo: FaceIdRepo, face_app, images_root: str = "images/persons"):
        self.repo = repo
        self.face_app = face_app
        self.images_root = images_root

    # 1) resolve/create person_id по sgb
    def resolve_person_id(self, sgb_person_id: int) -> str:
        pid = self.repo.get_person_id_by_sgb(sgb_person_id)
        if pid:
            return pid
        pid = new_uuid()
        self.repo.insert_person(pid)
        self.repo.upsert_sgb_map(sgb_person_id, pid, is_active=1)
        return pid

    # 2) process_photo improved
    async def process_photo(self, sgb_person_id: int, person_id: str, photo_b64: str) -> PhotoResult:
        try:
            img_bytes = decode_base64(photo_b64)
            img = decode_cv2(img_bytes)

            res = await asyncio.to_thread(
                get_face_embedding_strict,
                img,
                self.face_app,
                min_det_score=0.60,
                min_face_size=80,
                min_blur=60.0,
            )

            if res is None:
                face_url = f"{self.images_root}/low_quality/{sgb_person_id}/{person_id}.jpg"
                await save_bytes(face_url, img_bytes)
                return PhotoResult(face_url=face_url, polygons=zero_embedding(), embedding_status=EMB_LOW_QUALITY)

            face_url = f"{self.images_root}/{sgb_person_id}/{person_id}.jpg"
            await save_bytes(face_url, img_bytes)

            return PhotoResult(
                face_url=face_url,
                polygons=res.embedding,
                embedding_status=EMB_OK,
                det_score=res.meta.det_score,
                blur=res.meta.blur,
                face_size=res.meta.face_size,
                faces_found=res.meta.faces_found,
            )

        except (ImageError, Exception):
            return PhotoResult(face_url=None, polygons=zero_embedding(), embedding_status=EMB_LOW_QUALITY)

    # 3) fallback from docs (now includes metrics)
    def fallback_photo_from_documents(self, person_id: str) -> PhotoResult:
        latest = self.repo.get_latest_face_payload(person_id)
        if latest and latest.get("embedding_status") == EMB_OK and latest.get("face_url"):
            return PhotoResult(
                face_url=latest["face_url"],
                polygons=latest["polygons"] or zero_embedding(),
                embedding_status=EMB_OK,
                det_score=float(latest.get("det_score", 0.0)),
                blur=float(latest.get("blur", 0.0)),
                face_size=int(latest.get("face_size", 0)),
                faces_found=int(latest.get("faces_found", 0)),
            )
        return PhotoResult(face_url=None, polygons=zero_embedding(), embedding_status=EMB_NONE)

    def choose_best_photo(self, new_photo: PhotoResult, old_photo: PhotoResult) -> PhotoResult:
        """
        Защита: не ухудшаем качество.
        Если новый OK, но хуже старого OK — используем старое.
        """
        if new_photo.embedding_status != EMB_OK:
            return old_photo

        if old_photo.embedding_status != EMB_OK:
            return new_photo

        # сравниваем score
        new_q = quality_score(new_photo)
        old_q = quality_score(old_photo)

        # если новый заметно хуже — оставляем старый
        if new_q + 5.0 < old_q:  # порог "заметно"
            return old_photo

        return new_photo

    # 4) insert document snapshot WITH metrics
    def insert_document_snapshot(self, person_id: str, payload, photo: PhotoResult) -> None:
        self.repo.insert_document_snapshot({
            "id": new_uuid(),
            "person_id": person_id,
            "citizen": payload.citizen,
            "citizen_sgb": payload.citizen_sgb,
            "dtb": payload.date_of_birth,
            "passport": payload.passport_number,
            "passport_expired": payload.passport_expired,
            "sex": payload.sex,
            "full_name": payload.full_name,
            "face_url": photo.face_url,
            "polygons": photo.polygons,
            "embedding_status": photo.embedding_status,
            "det_score": float(photo.det_score or 0.0),
            "blur": float(photo.blur or 0.0),
            "face_size": int(photo.face_size or 0),
            "faces_found": int(photo.faces_found or 0),
        })

    # 5) insert border event
    def insert_border_event(self, person_id: str, payload) -> None:
        self.repo.insert_border_event({
            "id": new_uuid(),
            "border_id": payload.border_id,
            "person_id": person_id,
            "reg_date": payload.reg_date,
            "direction_country": payload.direction_country,
            "direction_country_sgb": payload.direction_country_sgb,
            "visa_type": payload.visa_type,
            "visa_number": payload.visa_number,
            "visa_organ": payload.visa_organ,
            "visa_date_from": payload.visa_date_from,
            "visa_date_to": payload.visa_date_to,
            "action": payload.action,
            "kpp": payload.kpp,
        })

    # 6) ingest - ENDI TAYYOR
    async def ingest(self, payload) -> str:
        # Qo'shimcha tekshiruvlar - agar validation endpointda qilinsa, bu yerda faqat service uchun
        person_id = self.resolve_person_id(payload.sgb_person_id)

        old_best = self.fallback_photo_from_documents(person_id)

        if payload.photo:
            new_photo = await self.process_photo(payload.sgb_person_id, person_id, payload.photo)
#
#             # Agar rasmda yuz aniqlanmasa, xato qaytarish
#             if new_photo.embedding_status == EMB_LOW_QUALITY:
#                 raise ValueError(
#                     "No valid face detected in the photo. "
#                     "Please ensure the photo meets these requirements:\n"
#                     "1. Face is clearly visible and frontal\n"
#                     "2. Good lighting conditions\n"
#                     "3. Face size is at least 80px\n"
#                     "4. Image is not blurry"
#                 )
        else:
            new_photo = PhotoResult(face_url=None, polygons=zero_embedding(), embedding_status=EMB_NONE)

        # выбираем лучшее (не ухудшаем)
        best_photo = self.choose_best_photo(new_photo, old_best)

        # Database operatsiyalarini bajarish
        try:
            self.insert_document_snapshot(person_id, payload, best_photo)
            self.insert_border_event(person_id, payload)
        except Exception as e:
            raise ValueError(f"Database error: {str(e)}")

        return person_id