from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.repositories.faceid_repo import FaceIdRepo
from app.services.utils import new_uuid
from app.services.image_service import decode_base64, decode_cv2, save_bytes, zero_embedding, ImageError
from app.services.face_pipeline import get_face_embedding_strict

EMB_OK = 1
EMB_NONE = 0
EMB_FAILED = 2

@dataclass
class PhotoResult:
    face_url: Optional[str]
    polygons: list[float]
    embedding_status: int
    # метрики (пока не пишем в БД, но можем логировать)
    det_score: Optional[float] = None
    blur: Optional[float] = None
    face_size: Optional[int] = None
    faces_found: Optional[int] = None

class ProviderIngestService:
    def __init__(self, repo: FaceIdRepo, face_app, images_root: str = "images/persons"):
        self.repo = repo
        self.face_app = face_app
        self.images_root = images_root

    # 1) resolve/create person_id по sgb
    def resolve_person_id(self, sgb_person_id: int) -> str:
        ZERO_UUID = "00000000-0000-0000-0000-000000000000"
        pid = self.repo.get_person_id_by_sgb(sgb_person_id)
        if pid:
                pid_str = str(pid)
                if pid_str != ZERO_UUID:
                    return pid_str

        pid = new_uuid()
        self.repo.insert_person(pid)
        self.repo.upsert_sgb_map(sgb_person_id, pid, is_active=1)
        return pid

    # 2) process_photo: decode → embedding → save → status (улучшено)
    async def process_photo(self, sgb_person_id: int, person_id: str, photo_b64: str) -> PhotoResult:
        try:
            img_bytes = decode_base64(photo_b64)
            img = decode_cv2(img_bytes)

            # CPU-bound: InsightFace внутри, запускаем в thread
            res = await __import__("asyncio").to_thread(
                get_face_embedding_strict,
                img,
                self.face_app,
                min_det_score=0.60,
                min_face_size=80,
                min_blur=60.0,
            )

            if res is None:
                return PhotoResult(face_url=None, polygons=zero_embedding(), embedding_status=EMB_FAILED)

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
            return PhotoResult(face_url=None, polygons=zero_embedding(), embedding_status=EMB_FAILED)

    # 3) fallback_photo_from_documents
    def fallback_photo_from_documents(self, person_id: str) -> PhotoResult:
        latest = self.repo.get_latest_face_payload(person_id)
        if latest and latest.get("embedding_status") == EMB_OK and latest.get("face_url"):
            return PhotoResult(
                face_url=latest["face_url"],
                polygons=latest["polygons"] or zero_embedding(),
                embedding_status=EMB_OK,
            )
        return PhotoResult(face_url=None, polygons=zero_embedding(), embedding_status=EMB_NONE)

    # 4) insert_document_snapshot
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


    # 5) insert_border_event
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
        })

    # 6) единый ingest
    async def ingest(self, payload) -> str:
        person_id = self.resolve_person_id(payload.sgb_person_id)

        if payload.photo:
            photo_res = await self.process_photo(payload.sgb_person_id, person_id, payload.photo)
            # если не получилось — пытаемся взять лучшее из истории
            if photo_res.embedding_status != EMB_OK:
                photo_res = self.fallback_photo_from_documents(person_id)
        else:
            # photo = null → всегда пробуем историю
            photo_res = self.fallback_photo_from_documents(person_id)

        self.insert_document_snapshot(person_id, payload, photo_res)
        self.insert_border_event(person_id, payload)

        return person_id
