# app/utils/response.py
from typing import Any, Dict

def success(data: Any = None, message: str = "Success", **kwargs) -> Dict:
    """Success response formatter"""
    response = {
        "status": "ok",
        "message": message,
        **kwargs
    }
    if data is not None:
        response["data"] = data
    return response

def error(message: str = "Error", code: str = None, **kwargs) -> Dict:
    """Error response formatter"""
    response = {
        "status": "error",
        "message": message,
        **kwargs
    }
    if code:
        response["code"] = code
    return response