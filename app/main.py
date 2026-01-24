from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import provider, search
from app.services.face_recognition import create_face_app

import logging

# -------------------------
# APP INIT
# -------------------------
app = FastAPI(
    title="Universal API",
    version="1.0",
    docs_url="/docs",      # Swagger ON
    redoc_url="/redoc",    # ReDoc ON
    openapi_url="/openapi.json"
)

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# VALIDATION ERROR HANDLER
# -------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = []

    for error in errors:
        field = error["loc"][-1] if error["loc"] else "unknown"
        messages.append(f"{field}: {error['msg']}")

    return JSONResponse(
        status_code=200,
        content={
            "status": "error",
            "message": "; ".join(messages),
            "person_id": None
        }
    )

# -------------------------
# ROUTERS
# -------------------------
app.include_router(provider.router, prefix="/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/search", tags=["Search"])

# -------------------------
# STARTUP (MODEL LOAD)
# -------------------------
@app.on_event("startup")
async def load_model_once():
    try:
        app.state.face_app = create_face_app()
        logging.info("Face recognition model loaded successfully")
    except Exception as e:
        logging.error(f"Model load failed: {e}")
        app.state.face_app = None  # server yiqilmasin

# -------------------------
# ROOT
# -------------------------
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "FastAPI server is running"
    }