# app/api/provider.py
from fastapi import APIRouter, Request
from app.services.database import client
from app.utils.validation import validate_all_fields, ValidationError
from app.utils.response import success, error
from app.schemas.provider import ProviderPersonIn
from app.repositories.faceid_repo import FaceIdRepo
from app.services.provider_ingest_service import ProviderIngestService
from app.schemas.common import PersonResponse

router = APIRouter()

def build_service(request: Request) -> ProviderIngestService:
    face_app = request.app.state.face_app
    repo = FaceIdRepo(client)
    return ProviderIngestService(repo=repo, face_app=face_app)

def transform_codes(payload):
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

@router.post(
    "/register-persons",
    response_model=PersonResponse,
    summary="Register person from provider system",
    description="""
Registers a person using provider data.

### Always returns HTTP 200

Check `status` field:
- `ok`    → success
- `error` → validation or business error
""",
    responses={
        200: {
            "description": "Success or error response",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Successful registration",
                            "value": {
                                "status": "ok",
                                "message": "Person registered successfully",
                                "person_id": 123
                            }
                        },
                        "error": {
                            "summary": "Error",
                            "value": {
                                "status": "error",
                                "message": "visa_type: All visa fields must be provided together or none at all",
                                "person_id": None
                            }
                        }
                    }
                }
            }
        },
        422: {
                "description": "Hidden",
                "content": {}
        }
    }
)
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
        return success(
            message="Person registered successfully",
            person_id=person_id
        )

    except ValidationError as e:
        error_msg = f"{e.message}"
        if e.field:
            error_msg = f"{e.field}: {e.message}"

        return error(message=error_msg, person_id=None)

    except ValueError as e:
        return error(message=str(e), person_id=None)

    except Exception as e:
        error_msg = str(e)

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

        return error(message=error_msg, person_id=None)