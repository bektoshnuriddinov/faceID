from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import asyncio

from app.repositories.search_repo import SearchRepo
from app.services.image_service import decode_base64, decode_cv2, ImageError
from app.services.face_search_pipeline import detect_all_faces_strict, FaceFound


# =========================
# Confidence thresholds
# =========================

STRONG_MATCH_MAX_DIST = 0.25
MAYBE_MATCH_MAX_DIST  = 0.35


def classify_confidence(distance: float) -> str:
    if distance <= STRONG_MATCH_MAX_DIST:
        return "strong"
    if distance <= MAYBE_MATCH_MAX_DIST:
        return "maybe"
    return "weak"


# =========================
# Filters
# =========================

@dataclass
class SearchFilters:
    citizen: Optional[int] = None
    dtb: Optional[str] = None        # 'YYYY-MM-DD'
    passport: Optional[str] = None


# =========================
# Service
# =========================

class SearchService:
    def __init__(self, repo: SearchRepo, face_app):
        self.repo = repo
        self.face_app = face_app

    async def search_by_image_b64(
        self,
        image_b64: str,
        *,
        top_k: int = 10,
        ef_search: Optional[int] = None,
        filters: Optional[SearchFilters] = None
    ) -> Dict[str, Any]:
        """
        Main face search entrypoint.
        """

        # clean base64 (for response)
        source_image_b64 = (
            image_b64.split("base64,", 1)[1]
            if "base64," in image_b64
            else image_b64
        )

        # -------------------------
        # Decode image
        # -------------------------
        try:
            img_bytes = decode_base64(image_b64)
            img = decode_cv2(img_bytes)
        except ImageError as e:
            return {
                "status": "error",
                "message": str(e),
            }

        # -------------------------
        # Detect faces (CPU-bound)
        # -------------------------
        faces: List[FaceFound] = await asyncio.to_thread(
            detect_all_faces_strict,
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
                "source_image_base64": source_image_b64,
                "faces": [],
            }

        f = filters or SearchFilters()

        # -------------------------
        # Search per face
        # -------------------------
        per_face_candidates: List[List[Dict[str, Any]]] = []
        all_person_ids: List[str] = []

        for face in faces:
            cands = self.repo.search_similar_people(
                face.embedding,
                top_k=top_k,
                ef_search=ef_search,
                citizen=f.citizen,
                dtb=f.dtb,
                passport=f.passport,
            )
            per_face_candidates.append(cands)
            all_person_ids.extend([c["person_id"] for c in cands])

        # -------------------------
        # Batch-load related data
        # -------------------------
        uniq_ids = list(dict.fromkeys(all_person_ids))

        profiles = self.repo.load_profiles(uniq_ids)
        sgb_map = self.repo.load_sgb_ids(uniq_ids)
        last_moves = self.repo.load_last_entry_exit(uniq_ids)

        # -------------------------
        # Build response
        # -------------------------
        faces_out: List[Dict[str, Any]] = []

        for idx, face in enumerate(faces):
            matches = []

            for cand in per_face_candidates[idx]:
                pid = cand["person_id"]
                profile = profiles.get(pid, {})
                move = last_moves.get(pid, {})

                matches.append({
                    "person_id": pid,
                    "sgb_person_id": sgb_map.get(pid),
                    "distance": cand["distance"],
                    "confidence": classify_confidence(cand["distance"]),

                    "found_face_url": cand.get("found_face_url"),
                    "current_face_url": profile.get("face_url"),

                    "full_name": profile.get("full_name"),
                    "dtb": str(profile.get("dtb")) if profile.get("dtb") else None,
                    "sex": profile.get("sex"),
                    "passport": profile.get("passport"),
                    "citizen": profile.get("citizen"),
                    "citizen_sgb": profile.get("citizen_sgb"),

                    "last_entry": move.get("last_entry"),
                    "last_exit": move.get("last_exit"),
                })

            faces_out.append({
                "face_index": idx,
                "source_face_base64": face.face_b64,
                "meta": {
                    "bbox": face.bbox,
                    "det_score": face.det_score,
                    "blur": face.blur,
                    "face_size": face.face_size,
                    "faces_found_in_image": len(faces),
                },
                "matches": matches,
            })

        msg = (
            "Single-face search"
            if len(faces_out) == 1
            else f"Multi-face search: {len(faces_out)} faces"
        )

        return {
            "status": "ok",
            "message": msg,
            "source_image_base64": source_image_b64,
            "faces": faces_out,
        }
