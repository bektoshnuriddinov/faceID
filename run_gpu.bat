@echo off
echo ===============================
echo START SPOOFING FASTAPI
echo ===============================

REM -------------------------------
REM CUDA
REM -------------------------------
set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.4"
set "PATH=%CUDA_PATH%\bin;%CUDA_PATH%\libnvvp;%PATH%"

REM -------------------------------
REM GO TO SPOOFING PROJECT ROOT
REM -------------------------------
cd /d C:\Users\Defender\programm\Deploy\SpoingFastApi

echo CURRENT DIR:
cd

REM -------------------------------
REM USE SPOOFING FASTAPI VENV
REM -------------------------------
set PYTHON=C:\Users\Defender\programm\Deploy\SpoingFastApi\fastapi\Scripts\python.exe

echo PYTHON:
"%PYTHON%" --version

REM -------------------------------
REM START UVICORN
REM -------------------------------
"%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 6666 --reload

pause
