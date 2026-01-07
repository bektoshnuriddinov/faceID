@echo off
set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.4"
set "PATH=%CUDA_PATH%\bin;%CUDA_PATH%\libnvvp;%PATH%"

call C:\Users\Defender\programm\Deploy\SpofingFastApi\fastapi\Scripts\activate.bat

echo Starting FastAPI server with auto-reload...
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

pause