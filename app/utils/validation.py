# app/utils/validation.py
import re
import base64
import binascii
from datetime import date, datetime
from typing import Optional

class ValidationError(Exception):
    """Custom validation error with field info"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_passport_number(passport_number: str) -> None:
    """Validate passport number format"""
    if not passport_number or not passport_number.strip():
        raise ValidationError("Passport number is required", "passport_number")

    passport_number = passport_number.strip()

    if len(passport_number) == 0:
        raise ValidationError("Passport number cannot be empty", "passport_number")


def validate_full_name(full_name: str) -> None:
    """Validate full name"""
    if not full_name or not full_name.strip():
        raise ValidationError("Full name is required", "full_name")

    full_name = full_name.strip()

    if len(full_name) == 0:
        raise ValidationError("Full name cannot be empty", "full_name")


def validate_date_of_birth(dob: date) -> None:
    """Validate date of birth"""
    pass


def validate_passport_expiry(expiry: Optional[date]) -> None:
    """Validate passport expiry date"""
    pass


def validate_sex(sex: int) -> None:
    """Validate sex code"""
    if sex not in [1, 2]:  # 1 for male, 2 for female
        raise ValidationError("Invalid sex code (must be 1 or 2)", "sex")


def validate_action(action: int) -> None:
    """Validate action code"""
    if action not in [1, 2]:  # 1 for entry, 2 for exit
        raise ValidationError("Invalid action (must be 1 or 2)", "action")


def validate_photo(photo: Optional[str]) -> None:
    """Validate photo (base64 or data-url)"""
    if photo is None:
        return

    try:
        # Check if it's a data URL
        if photo.startswith('data:image'):
            # Extract base64 part
            parts = photo.split(',', 1)
            if len(parts) != 2:
                raise ValidationError("Invalid data URL format", "photo")

            base64_data = parts[1]
            if not base64_data:
                raise ValidationError("Empty image data", "photo")

            # Validate base64
            try:
                base64.b64decode(base64_data, validate=True)
            except binascii.Error:
                raise ValidationError("Invalid base64 encoding", "photo")

        else:
            # Plain base64
            try:
                base64.b64decode(photo, validate=True)
            except binascii.Error:
                raise ValidationError("Invalid base64 encoding", "photo")

    except Exception as e:
        raise ValidationError(f"Invalid photo data: {str(e)}", "photo")


def validate_visa_dates(visa_date_from: Optional[date], visa_date_to: Optional[date]) -> None:
    """Validate visa dates"""
    if visa_date_from and visa_date_to and visa_date_to < visa_date_from:
        raise ValidationError("Visa end date cannot be before start date", "visa_date_to")


def validate_reg_date(reg_date: datetime) -> None:
    """Validate registration date"""
    pass


def validate_visa_fields_consistency(payload) -> None:
    """Validate visa fields consistency - hammasi to'liq yoki umuman yo'q"""
    visa_fields = [
        payload.visa_type,
        payload.visa_number,
        payload.visa_organ,
        payload.visa_date_from,
        payload.visa_date_to
    ]

    # None bo'lmagan fieldlar sonini hisoblaymiz
    non_null_count = sum(1 for field in visa_fields if field is not None)
    total_fields = len(visa_fields)

    # Agar 1-4 ta field berilgan bo'lsa (ya'ni hammasi emas)
    if 1 <= non_null_count < total_fields:
        raise ValidationError("All visa fields must be provided together or none at all", "visa_type")

    # Agar barcha fieldlar berilgan bo'lsa, ular bo'sh string emasligini tekshiramiz
    if non_null_count == total_fields:
        # String fieldlar bo'sh emasligini tekshirish
        if not payload.visa_type or not payload.visa_type.strip():
            raise ValidationError("Visa type cannot be empty when visa information is provided", "visa_type")

        if not payload.visa_number or not payload.visa_number.strip():
            raise ValidationError("Visa number cannot be empty when visa information is provided", "visa_number")

        if not payload.visa_organ or not payload.visa_organ.strip():
            raise ValidationError("Visa organ cannot be empty when visa information is provided", "visa_organ")

def validate_date_of_birth_range(
    date_from: Optional[date],
    date_to: Optional[date]
) -> None:
    """
    date_of_birth_from va date_of_birth_to:
    - ikkalasi birga kelishi shart
    - yoki ikkalasi ham yo‘q bo‘lishi kerak
    """

    # bittasi bor, bittasi yo‘q
    if (date_from is None) ^ (date_to is None):
        raise ValidationError(
            "date_of_birth_from and date_of_birth_to must be provided together",
            "date_of_birth_from"
        )

    # ikkalasi ham yo‘q — OK
    if date_from is None and date_to is None:
        return

    today = date.today()

    # kelajak sanasi bo‘lmasin
    if date_from > today or date_to > today:
        raise ValidationError(
            "date_of_birth cannot be in the future",
            "date_of_birth_from"
        )

    # juda eski bo‘lmasin
    if date_from.year < 1900 or date_to.year < 1900:
        raise ValidationError(
            "date_of_birth is too old",
            "date_of_birth_from"
        )

    # from <= to
    if date_from > date_to:
        raise ValidationError(
            "date_of_birth_from must be less than or equal to date_of_birth_to",
            "date_of_birth_from"
        )


def validate_all_fields(payload) -> None:
    """Validate all fields in payload"""

    # Required integer fields validation
    # sgb_person_id endi 0 dan boshlanishi mumkin
    if payload.border_id <= 0:
        raise ValidationError("Invalid border ID", "border_id")

    if payload.sgb_person_id < 0:  # 0 ham qabul qilinadi
        raise ValidationError("Invalid SGB person ID", "sgb_person_id")

    if payload.citizen <= 0:
        raise ValidationError("Invalid citizen code", "citizen")

    if payload.citizen_sgb <= 0:
        raise ValidationError("Invalid SGB citizen code", "citizen_sgb")

    if payload.direction_country <= 0:
        raise ValidationError("Invalid direction country", "direction_country")

    if payload.direction_country_sgb <= 0:
        raise ValidationError("Invalid SGB direction country", "direction_country_sgb")

    # Required fields validation
    validate_passport_number(payload.passport_number)
    validate_full_name(payload.full_name)
    validate_sex(payload.sex)
    validate_action(payload.action)

    # Optional fields validation
    validate_photo(payload.photo)
    validate_visa_dates(payload.visa_date_from, payload.visa_date_to)

    # Visa fields consistency validation
    validate_visa_fields_consistency(payload)


def validate_search_fields(payload) -> None:
    """
    Search payload uchun validation
    """
    # photo tekshiruvi
    if not payload.photo_base64 or not payload.photo_base64.strip():
        raise ValidationError("photo_base64 is required", "photo_base64")

    # citizen
    if payload.citizen is not None and payload.citizen <= 0:
        raise ValidationError("Invalid citizen code", "citizen")

    # date range
    validate_date_of_birth_range(
        payload.date_of_birth_from,
        payload.date_of_birth_to
    )

