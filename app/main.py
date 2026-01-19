from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth
from app.api import provider,search
from app.services.face_recognition import create_face_app


app = FastAPI(title="Universal API", version="1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic validation errors uchun exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Pydantic validatsiya xatolarini o'zimizning formatimizga o'tkazamiz
    errors = exc.errors()
    messages = []

    for error in errors:
        # Field nomini olish
        if len(error["loc"]) > 1:
            field = error["loc"][1]  # body -> field_name
        else:
            field = error["loc"][0] if error["loc"] else "unknown"

        # Xabar matnini olish va tozalash
        msg = error["msg"]
        messages.append(f"{field}: {msg}")

    error_message = "; ".join(messages)

    return JSONResponse(
        status_code=200,  # HTTP 200 qaytaramiz, lekin ichida status: "error"
        content={
            "status": "error",
            "message": error_message,
            "person_id": None
        }
    )

# Router ni qo'shish
app.include_router(provider.router, prefix="/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/search", tags=["Search"])

@app.on_event("startup")
async def load_model_once():
    app.state.face_app = create_face_app(providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

@app.get("/")
async def root():
    return {"message": "FastAPI server is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=6666)