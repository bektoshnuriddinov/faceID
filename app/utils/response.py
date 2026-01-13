from fastapi.responses import JSONResponse

def success(message: str, data: dict = None, code: int = 200):
    payload = {
        "status": "ok",
        "message": message
    }
    if data:
        payload["data"] = data
    return JSONResponse(status_code=code, content=payload)


def error(message: str, code: int = 400):
    return JSONResponse(
        status_code=code,
        content={
            "status": "error",
            "message": message
        }
    )