@echo off
chcp 65001
REM -----------------------------------------------------------------
REM 데이터베이스 서비스 시작 (자동 시작 설정되어 있다면 이 줄은 건너뛰어도 됨)
REM PostgreSQL 서비스 이름은 설치된 버전에 따라 다를 수 있음.
REM 예를 들어, postgresql-x64-17 또는 postgresql-x64-13 등으로 되어 있을 수 있음.
REM PostgreSQL 서비스 상태 확인 후 시작
echo 데이터베이스 서비스 시작 중...
net start postgresql-x64-17
if %ERRORLEVEL% neq 0 (
    echo PostgreSQL 서비스 시작 실패 또는 이미 실행 중입니다.
) else (
    echo PostgreSQL 서비스가 성공적으로 시작되었습니다.
)

REM -----------------------------------------------------------------
REM 특정 폴더로 이동 (가상환경이 위치한 경로로 이동)
echo 가상환경 폴더로 이동 중...
cd D:\DTP\DTP\data\distopia_api

REM 가상환경 활성화 (경로는 본인의 가상환경 경로로 변경)
echo 가상환경 활성화 중...
call D:\DTP\DTP\data\distopia_api\venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo 가상환경 활성화 실패
    exit /b
) else (
    echo 가상환경 활성화 성공
)

REM -----------------------------------------------------------------
REM FastAPI 서버 실행 (HTTPS 환경, 포트 8001)
REM uvicorn이 설치되어 있어야 하며 시스템 PATH에 등록되어 있어야 합니다.
REM distopia_api 모듈 경로가 올바르게 지정되어 있는지 확인 필요

REM 환경 변수로 경로 추가 (distopia_api 모듈이 있는 경로)
set PYTHONPATH=D:\DTP\DTP\data

REM FastAPI 서버 실행
echo FastAPI 서버 실행 중...
uvicorn distopia_api.main:app --host 127.0.0.1 --port 8001 --ssl-keyfile="D:\DTP\DTP\data\key.pem" --ssl-certfile="D:\DTP\DTP\data\cert.pem"

REM 서버 실행 후 로그를 기다리기 위해 pause 명령어 추가
pause
