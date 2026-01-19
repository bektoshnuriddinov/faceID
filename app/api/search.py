from fastapi import APIRouter, Request, UploadFile, File, Form
from typing import Optional

from app.services.database import client
from app.repositories.search_repo import SearchRepo
from app.services.search_service import SearchService, SearchFilters
from app.schemas.search import SearchByPhotoIn

router = APIRouter()

def build_search_service(request: Request) -> SearchService:
    face_app = request.app.state.face_app
    repo = SearchRepo(client)
    return SearchService(repo=repo, face_app=face_app)

@router.post("/people/by-photo")
async def search_people_by_photo(
    request: Request,
    payload: SearchByPhotoIn
):
    svc = build_search_service(request)

    filters = SearchFilters(
        citizen=payload.citizen,
        dtb=payload.date_of_birth,
        passport=payload.passport
    )

    return await svc.search_by_image_b64(
        payload.photo_base64,
        top_k=payload.top_k,
        ef_search=payload.ef_search,
        filters=filters
    )


@router.post("/people/by-photo-file")
async def search_people_by_photo_file(
    request: Request,
    file: UploadFile = File(...),
    top_k: int = Form(10),
    ef_search: Optional[int] = Form(None),
    passport: Optional[str] = Form(None),
    citizen: Optional[int] = Form(None),
    date_of_birth: Optional[str] = Form(None),  # YYYY-MM-DD
):
    content = await file.read()
    # превращаем файл в base64, чтобы ответ всегда содержал source_image_base64
    import base64
    photo_b64 = base64.b64encode(content).decode("ascii")

    svc = build_search_service(request)
    filters = SearchFilters(
        citizen=citizen,
        dtb=date_of_birth,
        passport=passport
    )
    return await svc.search_by_image_b64(photo_b64, top_k=top_k, ef_search=ef_search, filters=filters)
