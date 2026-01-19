# app/schemas/provider.py
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime

class ProviderPersonIn(BaseModel):
    border_id: int
    sgb_person_id: int  # Endi 0 ham bo'lishi mumkin
    citizen: int
    citizen_sgb: int
    date_of_birth: date
    passport_number: str = Field(min_length=1, max_length=64)
    passport_expired: Optional[date] = None
    sex: int
    full_name: str = Field(min_length=1, max_length=255)
    photo: Optional[str] = None
    reg_date: datetime
    direction_country: int
    direction_country_sgb: int
    action: int
    visa_type: Optional[str] = None
    visa_number: Optional[str] = None
    visa_organ: Optional[str] = None
    visa_date_from: Optional[date] = None
    visa_date_to: Optional[date] = None
    kpp: Optional[str] = None

    @validator('sgb_person_id')
    def validate_sgb_person_id(cls, v):
        if v < 0:
            raise ValueError('SGB person ID cannot be negative')
        return v

    @validator('sex')
    def validate_sex(cls, v):
        if v not in [1, 2]:
            raise ValueError('Sex must be 1 (male) or 2 (female)')
        return v

    @validator('action')
    def validate_action(cls, v):
        if v not in [1, 2]:
            raise ValueError('Action must be 1 (entry) or 2 (exit)')
        return v

    class Config:
        extra = 'ignore'