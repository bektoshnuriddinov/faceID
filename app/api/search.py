# app/api/search.py
from fastapi import APIRouter, Request
from app.services.database import client
from app.utils.validation import validate_all_fields, ValidationError, validate_search_fields
from app.schemas.search import SearchByPhotoIn
from app.repositories.search_repo import SearchRepo
from app.services.search_service import SearchService

router = APIRouter()

def build_service(request: Request) -> SearchService:
    face_app = request.app.state.face_app
    repo = SearchRepo(client)
    return SearchService(repo=repo, face_app=face_app)

@router.post("/search-by-photo")
async def search_by_photo(request: Request, payload: SearchByPhotoIn):
    try:
        validate_search_fields(payload)

        service = build_service(request)
        result = await service.search(payload)

        return {
            "status": "ok",
            "data": result
        }

    except ValidationError as e:
        msg = e.message
        if e.field:
            msg = f"{e.field}: {e.message}"

        return {
            "status": "error",
            "message": msg,
            "data": None
        }

    except ValueError as e:
        return {
            "status": "error",
            "message": str(e),
            "data": None
        }

    except Exception as e:
        error_msg = str(e)

        if "validation" in error_msg.lower():
            lines = error_msg.split('\n')
            if len(lines) >= 2:
                for i, line in enumerate(lines):
                    if "Input should be a valid date" in line:
                        if i > 0:
                            field = lines[i-1].strip()
                            msg = line.strip()
                            error_msg = f"{field}: {msg}"
                            break

        return {
            "status": "error",
            "message": error_msg,
            "data": None
        }
