# app/schemas/search.py
from pydantic import BaseModel
from typing import Optional
from datetime import date

class SearchByPhotoIn(BaseModel):
    photo_base64: str
    top_k: int = 10
    ef_search: Optional[int] = None
    passport: Optional[str] = None
    citizen: Optional[int] = None
    date_of_birth: Optional[date] = None

    class Config:
        extra = "ignore"
