from __future__ import annotations
from typing import Optional, List, Dict, Any


class SearchRepo:
    def __init__(self, client):
        self.client = client

    # ==========================================================
    # Face similarity search (core)
    # ==========================================================
    def search_similar_people(
        self,
        ref_vec: List[float],
        *,
        top_k: int = 10,
        ef_search: Optional[int] = None,
        citizen: Optional[int] = None,
        dtb_from: Optional[str] = None,
        dtb_to: Optional[str] = None,
        max_distance: float = 0.75,
    ) -> List[Dict[str, Any]]:

        where = [
            "has_embedding = 1",
            "cosineDistance(polygons, reference_vec) <= %(max_distance)s"
        ]

        params: Dict[str, Any] = {
            "ref": ref_vec,
            "max_distance": max_distance,
        }

        if citizen is not None:
            where.append("citizen = %(citizen)s")
            params["citizen"] = int(citizen)

        if dtb_from is not None:
            where.append("dtb >= toDate32(%(dtb_from)s)")
            params["dtb_from"] = dtb_from

        if dtb_to is not None:
            where.append("dtb <= toDate32(%(dtb_to)s)")
            params["dtb_to"] = dtb_to

        where_sql = " AND ".join(where)

        settings_sql = ""
        if ef_search is not None:
            settings_sql = (
                f" SETTINGS hnsw_candidate_list_size_for_search = {int(ef_search)}"
            )

        rows = self.client.execute(
            f"""
            WITH %(ref)s AS reference_vec
            SELECT
                person_id,
                cosineDistance(polygons, reference_vec) AS distance
            FROM person_documents_v2
            WHERE {where_sql}
            ORDER BY distance ASC
            LIMIT 1 BY person_id
            LIMIT {int(top_k)}
            {settings_sql}
            """,
            params,
        )

        return [
            {
                "person_id": r[0],
                "distance": float(r[1]),
            }
            for r in rows
        ]

    # ==========================================================
    # Load current profile snapshot
    # ==========================================================
    def load_profiles(self, person_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not person_ids:
            return {}

        ids = tuple(person_ids)

        rows = self.client.execute(
            """
            SELECT
                person_id,
                argMax(full_name, version)        AS full_name,
                argMax(dtb, version)              AS dtb,
                argMax(sex, version)              AS sex,
                argMax(citizen, version)          AS citizen,
                argMax(citizen_sgb, version)      AS citizen_sgb,
                argMax(passport, version)  AS passport,
                argMax(passport_expired, version) AS passport_expired
            FROM person_documents_v2
            WHERE person_id IN %(ids)s
            GROUP BY person_id
            """,
            {"ids": ids},
        )

        out: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            out[r[0]] = {
                "full_name": r[1],
                "dtb": r[2],
                "sex": int(r[3]) if r[3] is not None else None,
                "citizen": int(r[4]) if r[4] is not None else None,
                "citizen_sgb": int(r[5]) if r[5] is not None else None,
                "passport": r[6],
                "passport_expired": r[7],
            }

        return out

    # ==========================================================
    # Load active SGB person id
    # ==========================================================
    def load_sgb_ids(self, person_ids: List[str]) -> Dict[str, int]:
        if not person_ids:
            return {}

        ids = tuple(person_ids)

        rows = self.client.execute(
            """
            SELECT
                person_id,
                argMax(sgb_person_id, version) AS sgb_person_id
            FROM person_sgb_map_v2
            WHERE person_id IN %(ids)s
              AND is_active = 1
            GROUP BY person_id
            """,
            {"ids": ids},
        )

        return {r[0]: int(r[1]) for r in rows if r[1] is not None}

    # ==========================================================
    # Load last entry / exit + visa (SAFE)
    # ==========================================================
    def load_last_entry_exit(self, person_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not person_ids:
            return {}

        ids = tuple(person_ids)

        rows = self.client.execute(
            """
            WITH dedup AS
            (
                SELECT
                    person_id,
                    border_id,
                    kpp,
                    action,
                    argMax(reg_date, version) AS reg_date,

                    argMax(direction_country, version) AS direction_country,
                    argMax(direction_country_sgb, version) AS direction_country_sgb,

                    argMax(visa_type, version) AS visa_type,
                    argMax(visa_number, version) AS visa_number,
                    argMax(visa_organ, version) AS visa_organ,
                    argMax(visa_date_from, version) AS visa_date_from,
                    argMax(visa_date_to, version) AS visa_date_to
                FROM person_borders_v2
                WHERE person_id IN %(ids)s
                GROUP BY person_id, border_id, kpp, action
            )
            SELECT
                person_id,

                -- ========== LAST ENTRY ==========
                maxIf(reg_date, action = 1) AS entry_date,
                argMaxIf(border_id, reg_date, action = 1) AS entry_border_id,
                argMaxIf(kpp, reg_date, action = 1) AS entry_kpp,

                argMaxIf(direction_country, reg_date, action = 1) AS entry_direction_country,
                argMaxIf(direction_country_sgb, reg_date, action = 1) AS entry_direction_country_sgb,

                argMaxIf(visa_type, reg_date, action = 1) AS entry_visa_type,
                argMaxIf(visa_number, reg_date, action = 1) AS entry_visa_number,
                argMaxIf(visa_organ, reg_date, action = 1) AS entry_visa_organ,
                argMaxIf(visa_date_from, reg_date, action = 1) AS entry_visa_date_from,
                argMaxIf(visa_date_to, reg_date, action = 1) AS entry_visa_date_to,

                -- ========== LAST EXIT ==========
                maxIf(reg_date, action = 2) AS exit_date,
                argMaxIf(border_id, reg_date, action = 2) AS exit_border_id,
                argMaxIf(kpp, reg_date, action = 2) AS exit_kpp,

                argMaxIf(direction_country, reg_date, action = 2) AS exit_direction_country,
                argMaxIf(direction_country_sgb, reg_date, action = 2) AS exit_direction_country_sgb,

                argMaxIf(visa_type, reg_date, action = 2) AS exit_visa_type,
                argMaxIf(visa_number, reg_date, action = 2) AS exit_visa_number,
                argMaxIf(visa_organ, reg_date, action = 2) AS exit_visa_organ,
                argMaxIf(visa_date_from, reg_date, action = 2) AS exit_visa_date_from,
                argMaxIf(visa_date_to, reg_date, action = 2) AS exit_visa_date_to
            FROM dedup
            GROUP BY person_id
            """,
            {"ids": ids},
        )

        out: Dict[str, Dict[str, Any]] = {}

        for r in rows:
            out[r[0]] = {
                "last_entry": {
                    "reg_date": r[1],
                    "border_id": r[2],   # event id
                    "kpp": r[3],         # REAL CHECKPOINT
                    "direction_country": r[4],
                    "direction_country_sgb": r[5],
                    "visa": {
                        "type": r[6],
                        "number": r[7],
                        "organ": r[8],
                        "date_from": r[9],
                        "date_to": r[10],
                    } if r[6] else {},
                } if r[1] else {},

                "last_exit": {
                    "reg_date": r[11],
                    "border_id": r[12],
                    "kpp": r[13],
                    "direction_country": r[14],
                    "direction_country_sgb": r[15],
                    "visa": {
                        "type": r[16],
                        "number": r[17],
                        "organ": r[18],
                        "date_from": r[19],
                        "date_to": r[20],
                    } if r[16] else {},
                } if r[11] else {},
            }

        return out

