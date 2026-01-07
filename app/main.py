from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routes import auth
from app.services.face_recognition import create_face_app


app = FastAPI(title="Universal API", version="1.0")

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

@app.on_event("startup")
async def load_model_once():
    app.state.face_app = create_face_app(providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
@app.get("/")
async def root():
    return {"message": "FastAPI server is running!"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=6666)
