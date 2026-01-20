# app/schemas/search.py
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime

class SearchByPhotoIn(BaseModel):
    photo_base64: str
    citizen: Optional[int] = None

    date_of_birth_from: Optional[date] = None
    date_of_birth_to: Optional[date] = None

    # ----------------
    # FIELD VALIDATION
    # ----------------

    @validator("photo_base64")
    def photo_required(cls, v):
        if not v or not v.strip():
            raise ValueError("photo_base64 is required")
        return v

    @validator("citizen")
    def citizen_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("citizen must be positive")
        return v

    @validator("date_of_birth_from", "date_of_birth_to")
    def dob_basic_validation(cls, v):
        if v is None:
            return v

        today = date.today()

        if v > today:
            raise ValueError("date_of_birth cannot be in the future")

        if v.year < 1900:
            raise ValueError("date_of_birth is too old")

        return v

    class Config:
        extra = "ignore"
