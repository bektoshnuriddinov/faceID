from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import asyncio

from app.repositories.search_repo import SearchRepo
from app.services.image_service import decode_base64, decode_cv2, ImageError
from app.services.face_search_pipeline import (
    detect_all_faces_with_quality,
    FaceCandidate,
)

# ==========================================================
# Match classification
# ==========================================================

STRONG_MATCH_MAX_DIST = 0.25
MAYBE_MATCH_MAX_DIST = 0.75


def classify_confidence(distance: float) -> str:
    if distance <= STRONG_MATCH_MAX_DIST:
        return "strong"
    if distance <= MAYBE_MATCH_MAX_DIST:
        return "maybe"
    return "weak"


def distance_to_accuracy(distance: float) -> float:
    return round((1.0 - distance) * 100, 2)


# ==========================================================
# Filters
# ==========================================================

@dataclass
class SearchFilters:
    citizen: Optional[int] = None
    dtb_from: Optional[str] = None
    dtb_to: Optional[str] = None


# ==========================================================
# Service
# ==========================================================

class SearchService:
    def __init__(self, repo: SearchRepo, face_app):
        self.repo = repo
        self.face_app = face_app

    # ------------------------------------------------------
    # API entrypoint
    # ------------------------------------------------------
    async def search(self, payload) -> Dict[str, Any]:
        filters = SearchFilters(
            citizen=payload.citizen,
            dtb_from=str(payload.date_of_birth_from)
            if payload.date_of_birth_from else None,
            dtb_to=str(payload.date_of_birth_to)
            if payload.date_of_birth_to else None,
        )

        return await self.search_by_image_b64(
            payload.photo_base64,
            filters=filters,
        )

    # ------------------------------------------------------
    # Core search logic
    # ------------------------------------------------------
    async def search_by_image_b64(
        self,
        image_b64: str,
        *,
        top_k: int = 10,
        ef_search: Optional[int] = None,
        filters: Optional[SearchFilters] = None,
    ) -> Dict[str, Any]:

        source_image_base64 = (
            image_b64.split("base64,", 1)[1]
            if "base64," in image_b64
            else image_b64
        )

        # -------------------------
        # Decode image
        # -------------------------
        try:
            img = decode_cv2(decode_base64(image_b64))
        except ImageError as e:
            return {
                "status": "error",
                "message": str(e),
                "faces": None,
            }

        # -------------------------
        # Detect faces with quality
        # -------------------------
        faces: List[FaceCandidate] = await asyncio.to_thread(
            detect_all_faces_with_quality,
            img,
            self.face_app,
            min_det_score=0.60,
            min_face_size=80,
            min_blur=60.0,
            max_faces=10,
        )

        if not faces:
            return {
                "status": "ok",
                "message": "No faces detected",
                "source_image_base64": source_image_base64,
                "faces": [],
            }

        f = filters or SearchFilters()
        faces_out: List[Dict[str, Any]] = []
        quality_warning = False

        # ==================================================
        # Process each detected face
        # ==================================================
        for face_index, face in enumerate(faces):

            # -------------------------
            # Always prepare base face response
            # -------------------------
            face_result = {
                "face_index": face_index,
                "quality_ok": face.quality_ok,
                "quality_issues": face.quality_issues,
                "crop_face_base64": face.face_b64,
                "meta": {
                    "bbox": face.bbox,
                    "det_score": face.det_score,
                    "blur": face.blur,
                    "face_size": face.face_size,
                },
                "matches": [],
            }

            # -------------------------
            # If face quality is bad → no DB search
            # -------------------------
            if not face.quality_ok or not face.embedding:
                quality_warning = True
                faces_out.append(face_result)
                continue

            # -------------------------
            # 1️⃣ Search similar people
            # -------------------------
            candidates = self.repo.search_similar_people(
                face.embedding,
                top_k=top_k,
                ef_search=ef_search,
                citizen=f.citizen,
                dtb_from=f.dtb_from,
                dtb_to=f.dtb_to,
            )

            if not candidates:
                faces_out.append(face_result)
                continue

            # -------------------------
            # 2️⃣ Collect ALL person_ids (before filtering)
            # -------------------------
            person_ids = [c["person_id"] for c in candidates]
            uniq_ids = list(dict.fromkeys(person_ids))

            # -------------------------
            # 3️⃣ Load all related data
            # -------------------------
            profiles = self.repo.load_profiles(uniq_ids)
            sgb_ids = self.repo.load_sgb_ids(uniq_ids)
            borders = self.repo.load_last_entry_exit(uniq_ids)

            # -------------------------
            # 4️⃣ Build matches (filter weak HERE)
            # -------------------------
            matches: List[Dict[str, Any]] = []

            for c in candidates:
                distance = c["distance"]
                confidence = classify_confidence(distance)

                if confidence == "weak":
                    continue

                pid = c["person_id"]
                profile = profiles.get(pid, {})
                border = borders.get(pid, {})

                matches.append({
                    "person": {
                        "person_id": pid,
                        "sgb_person_id": sgb_ids.get(pid),

                        "full_name": profile.get("full_name"),
                        "dtb": str(profile.get("dtb"))
                        if profile.get("dtb") else None,
                        "sex": profile.get("sex"),
                        "citizen": profile.get("citizen"),
                        "citizen_sgb": profile.get("citizen_sgb"),
#                         "face_url": profile.get("face_url"),

                        "last_entry": border.get("last_entry"),
                        "last_exit": border.get("last_exit"),
                    },
                    "match": {
                        "distance": distance,
                        "accuracy": distance_to_accuracy(distance),
                        "confidence": confidence,
#                         "found_face_url": c.get("found_face_url"),
                    },
                })

            face_result["matches"] = matches
            faces_out.append(face_result)

        # ==================================================
        # Final response
        # ==================================================
        return {
            "status": "ok",
            "message": (
                "Single-face search"
                if len(faces_out) == 1
                else f"Multi-face search: {len(faces_out)} faces"
            ),
#             "source_image_base64": source_image_base64,
            "quality_warning": (
                "Some faces do not meet quality requirements. "
                "Results for those faces are not guaranteed."
                if quality_warning else None
            ),
            "faces": faces_out,
        }