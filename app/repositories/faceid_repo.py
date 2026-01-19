from __future__ import annotations
from typing import Optional, Dict, Any, List
from uuid import UUID

class FaceIdRepo:
    def __init__(self, client):
        self.client = client

    # --- mapping ---
    def get_person_id_by_sgb(self, sgb_person_id: int) -> Optional[str]:
        rows = self.client.execute(
            """
            SELECT argMax(person_id, version) AS person_id
            FROM person_sgb_map_v2
            WHERE sgb_person_id = %(sgb)s
            """,
            {"sgb": sgb_person_id},
        )
        ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")
        val = rows[0][0] if rows else None
        return None if val == ZERO_UUID else val

    def insert_person(self, person_id: str) -> None:
        self.client.execute(
            "INSERT INTO persons_v2 (id) VALUES",
            [{"id": person_id}],
        )

    def upsert_sgb_map(self, sgb_person_id: int, person_id: str, is_active: int = 1) -> None:
        self.client.execute(
            """
            INSERT INTO person_sgb_map_v2 (sgb_person_id, person_id, is_active)
            VALUES
            """,
            [{"sgb_person_id": sgb_person_id, "person_id": person_id, "is_active": is_active}],
        )

    # --- latest face payload (now WITH metrics) ---
    def get_latest_face_payload(self, person_id: str) -> Optional[Dict[str, Any]]:
        rows = self.client.execute(
            """
            SELECT
              argMax(face_url, version) AS face_url,
              argMax(polygons, version) AS polygons,
              argMax(embedding_status, version) AS embedding_status,
              argMax(det_score, version) AS det_score,
              argMax(blur, version) AS blur,
              argMax(face_size, version) AS face_size,
              argMax(faces_found, version) AS faces_found
            FROM person_documents_v2
            WHERE person_id = %(pid)s
            """,
            {"pid": person_id},
        )
        if not rows:
            return None

        face_url, polygons, embedding_status, det_score, blur, face_size, faces_found = rows[0]
        if embedding_status is None and face_url is None and not polygons:
            return None

        return {
            "face_url": face_url,
            "polygons": polygons,
            "embedding_status": int(embedding_status or 0),
            "det_score": float(det_score or 0.0),
            "blur": float(blur or 0.0),
            "face_size": int(face_size or 0),
            "faces_found": int(faces_found or 0),
        }

    # --- insert document snapshot WITH metrics ---
    def insert_document_snapshot(self, row: Dict[str, Any]) -> None:
        self.client.execute(
            """
            INSERT INTO person_documents_v2
            (id, person_id, citizen, citizen_sgb, dtb, passport, passport_expired,
             sex, full_name, face_url, polygons, embedding_status,
             det_score, blur, face_size, faces_found)
            VALUES
            """,
            [row],
        )

    # --- borders ---
    def insert_border_event(self, row: Dict[str, Any]) -> None:
        self.client.execute(
            """
            INSERT INTO person_borders_v2
            (id, border_id, person_id, reg_date, direction_country, direction_country_sgb,
             visa_type, visa_number, visa_organ, visa_date_from, visa_date_to, action, kpp)
            VALUES
            """,
            [row],
        )
