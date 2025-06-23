@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 한국어 음성 분석 파이프라인 실행 스크립트 (Windows)
REM conda activate ko_pipeline 환경에서 실행

echo 한국어 음성 분석 파이프라인 시작
echo ==================================

REM 현재 활성화된 conda 환경 확인
if "%CONDA_DEFAULT_ENV%"=="ko_pipeline" (
    echo conda 환경 확인: %CONDA_DEFAULT_ENV%
) else (
    echo 오류: ko_pipeline conda 환경이 활성화되지 않았습니다.
    echo    다음 명령어로 환경을 활성화하세요:
    echo    conda activate ko_pipeline
    pause
    exit /b 1
)

REM 현재 디렉토리를 프로젝트 루트로 설정
cd /d "%~dp0"
echo 작업 디렉토리: %CD%

REM .env 파일 존재 확인
if not exist ".env" (
    echo 오류: .env 파일이 없습니다.
    echo    .env.example을 참고하여 .env 파일을 생성하세요.
    pause
    exit /b 1
)

echo 환경변수 파일 확인: .env

REM Python 실행 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo 오류: Python이 설치되지 않았거나 PATH에 없습니다.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo Python 버전: %PYTHON_VERSION%

REM 필수 패키지 확인
echo 필수 패키지 확인 중...

set MISSING_PACKAGES=0

python -c "import fastapi" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import boto3" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import motor" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import aiomysql" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import openai" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import whisper" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import librosa" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import transformers" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import ffmpeg" >nul 2>&1 || set MISSING_PACKAGES=1
python -c "import dotenv" >nul 2>&1 || set MISSING_PACKAGES=1

if !MISSING_PACKAGES! equ 1 (
    echo 일부 필수 패키지가 설치되지 않았습니다.
    echo    다음 명령어로 설치하세요:
    echo    pip install -r requirements.txt
    pause
    exit /b 1
)

echo 필수 패키지 확인 완료

REM FFmpeg 설치 확인
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo 경고: FFmpeg이 설치되지 않았습니다.
    echo    오디오 변환에 문제가 있을 수 있습니다.
    echo    https://ffmpeg.org/download.html 에서 다운로드하세요.
    echo.
    set /p CONTINUE="계속 진행하시겠습니까? (y/N): "
    if /i not "!CONTINUE!"=="y" (
        echo 실행을 중단했습니다.
        pause
        exit /b 1
    )
) else (
    echo FFmpeg 확인 완료
)

REM 환경변수 확인
echo 환경변수 확인 중...

REM .env 파일에서 환경변수 로드 및 확인
for /f "tokens=1,2 delims==" %%a in ('type .env ^| findstr /v "^#" ^| findstr "="') do (
    set %%a=%%b
)

if "%AWS_ACCESS_KEY_ID%"=="" (
    echo AWS_ACCESS_KEY_ID가 설정되지 않았습니다.
    set ERROR_FOUND=1
)
if "%AWS_SECRET_ACCESS_KEY%"=="" (
    echo AWS_SECRET_ACCESS_KEY가 설정되지 않았습니다.
    set ERROR_FOUND=1
)
if "%OPENAI_API_KEY%"=="" (
    echo OPENAI_API_KEY가 설정되지 않았습니다.
    set ERROR_FOUND=1
)
if "%MONGODB_URI%"=="" (
    echo MONGODB_URI가 설정되지 않았습니다.
    set ERROR_FOUND=1
)
if "%MARIADB_HOST%"=="" (
    echo MARIADB_HOST가 설정되지 않았습니다.
    set ERROR_FOUND=1
)
if "%MARIADB_USER%"=="" (
    echo MARIADB_USER가 설정되지 않았습니다.
    set ERROR_FOUND=1
)
if "%MARIADB_PASSWORD%"=="" (
    echo MARIADB_PASSWORD가 설정되지 않았습니다.
    set ERROR_FOUND=1
)

if "%ERROR_FOUND%"=="1" (
    echo.
    echo    .env 파일을 확인하고 모든 필수 환경변수를 설정하세요.
    pause
    exit /b 1
)

echo 환경변수 확인 완료

REM 로그 디렉토리 생성
if not exist "logs" mkdir logs
echo 로그 디렉토리 준비 완료

REM 파이프라인 실행
echo.
echo 파이프라인 실행 중...
echo ==================================

REM Python 스크립트 실행
python run_pipeline.py

if errorlevel 1 (
    echo.
    echo ==================================
    echo 파이프라인 실행 실패
    echo 로그 파일: pipeline.log
    echo ==================================
    pause
    exit /b 1
) else (
    echo.
    echo ==================================
    echo 파이프라인 실행 완료!
    echo 로그 파일: pipeline.log
    echo ==================================
    pause
)

endlocal 