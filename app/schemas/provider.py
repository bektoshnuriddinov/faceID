# app/schemas/provider.py
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime

class ProviderPersonIn(BaseModel):
    border_id: int
    sgb_person_id: int  # Endi 0 ham bo'lishi mumkin
    citizen: int = Field(..., description="Citizen country code")
    citizen_sgb: int = Field(..., description="Citizen country code in SGB system")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    passport_number: str = Field(min_length=1, max_length=64, description="AA1234567 format")
    passport_expired: Optional[date] = Field(None, description="Passport expiration date in YYYY-MM-DD format")
    sex: int = Field(..., description="1 for male, 2 for female")
    full_name: str = Field(min_length=1, max_length=255)
    photo: Optional[str] = Field(None, description="Base64 encoded photo")
    reg_date: datetime = Field(..., description="Registration date and time in ISO 8601 format")
    direction_country: int = Field(..., description="Direction country code")
    direction_country_sgb: int = Field(..., description="Direction country code in SGB system")
    action: int = Field(..., description="1 for entry, 2 for exit")
    visa_type: Optional[str] = Field(None, description="Visa type. If provided, all other visa fields must also be provided.")
    visa_number: Optional[str] = Field(None, description="Visa number. Must be provided together with all other visa fields.")
    visa_organ: Optional[str] = Field(None, description="Visa issuing organization. Must be provided together with all other visa fields.")
    visa_date_from: Optional[date] = Field(None, description="Visa start date in YYYY-MM-DD format.Required if any visa field is present.")
    visa_date_to: Optional[date] = Field(None, description="Visa end date in YYYY-MM-DD format. Required if any visa field is present.")
    kpp: Optional[str] = Field(None, description="KPP code")

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