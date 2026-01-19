# app/api/provider.py
from fastapi import APIRouter, Request
from app.services.database import client
from app.utils.validation import validate_all_fields, ValidationError
from app.schemas.provider import ProviderPersonIn
from app.repositories.faceid_repo import FaceIdRepo
from app.services.provider_ingest_service import ProviderIngestService

router = APIRouter()

def build_service(request: Request) -> ProviderIngestService:
    face_app = request.app.state.face_app
    repo = FaceIdRepo(client)
    return ProviderIngestService(repo=repo, face_app=face_app)

def transform_codes(payload):
    """
    Kodlarni transformatsiya qilish:
    - citizen_sgb va direction_country_sgb: 170 -> 739001138
    - citizen va direction_country: 161 -> 246
    """
    # Original nusxasini saqlab qo'ymaslik uchun dict ga o'tkazamiz
    data = payload.dict()

    # Transformatsiyalar
    if data['citizen_sgb'] == 170:
        data['citizen_sgb'] = 739001138

    if data['direction_country_sgb'] == 170:
        data['direction_country_sgb'] = 739001138

    if data['citizen'] == 161:
        data['citizen'] = 246

    if data['direction_country'] == 161:
        data['direction_country'] = 246

    # Yangi payload yaratish
    return ProviderPersonIn(**data)

@router.post("/register-persons")
async def ingest_person(request: Request, payload: ProviderPersonIn):
    try:
        # 1. Kodlarni transformatsiya qilish
        payload = transform_codes(payload)

        # 2. Barcha maydonlarni validatsiya qilish
        validate_all_fields(payload)

        # 3. Serviceni chaqirish
        service = build_service(request)
        person_id = await service.ingest(payload)

        # 4. Muvaffaqiyatli response
        return {
            "status": "ok",
            "message": "Person registered successfully",
            "person_id": person_id
        }

    except ValidationError as e:
        # Validatsiya xatolari uchun
        error_msg = f"{e.message}"
        if e.field:
            error_msg = f"{e.field}: {e.message}"

        return {
            "status": "error",
            "message": error_msg,
            "person_id": None
        }

    except ValueError as e:
        # Service dan kelgan xatolar (face detection, database xatolari)
        return {
            "status": "error",
            "message": str(e),
            "person_id": None
        }

    except Exception as e:
        # Boshqa kutilmagan xatolar
        error_msg = str(e)

        # Pydantic validation xatolarini formatlash
        if "validation" in error_msg.lower():
            lines = error_msg.split('\n')
            if len(lines) >= 2:
                for i, line in enumerate(lines):
                    if "Input should be a valid date" in line or "value is outside expected range" in line:
                        if i > 0:
                            field = lines[i-1].strip()
                            msg = line.strip().replace('  ', '')
                            error_msg = f"{field}: {msg}"
                            break

        return {
            "status": "error",
            "message": error_msg,
            "person_id": None
        }