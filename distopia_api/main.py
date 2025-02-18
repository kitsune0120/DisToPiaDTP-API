import sys
import os
import shutil
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import openai

# ✅ 프로젝트 루트 경로 추가 (모듈 인식 문제 해결)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ✅ 내부 모듈 임포트
from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

# ✅ OpenAI API 키 설정 (GPT 사용 시 필요)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# ✅ 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# ✅ FastAPI 애플리케이션 생성
app = FastAPI(
    title="DTP 세계 확장 API",
    description="이 API는 DTP 세계관을 확장하는 기능을 제공합니다.",
    version="1.3"
)

# ✅ **📌 기본 라우트**
@app.get("/", summary="루트 페이지", description="API 서버가 정상적으로 실행 중인지 확인하는 엔드포인트입니다.")
def read_root():
    return {"message": "Hello, DisToPia!"}

@app.get("/home", summary="홈 페이지", description="DTP 세계관 API가 실행 중인지 확인하는 엔드포인트입니다.")
def home():
    return {"message": "DTP 세계관 API 실행 중!"}

# ✅ **📌 ZIP 파일 업로드 기능**
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # 업로드 디렉토리 자동 생성

@app.post("/upload-zip/", summary="ZIP 파일 업로드", description="ZIP 파일을 업로드하여 서버에 저장하는 기능입니다.")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="ZIP 파일만 업로드할 수 있습니다.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ ZIP 파일이 성공적으로 업로드 및 저장되었습니다!"}

# ✅ **📌 업로드된 파일 목록 조회 API**
@app.get("/uploaded-files/", summary="업로드된 파일 목록 조회", description="서버에 저장된 파일 목록을 반환합니다.")
def list_uploaded_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"uploaded_files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 존재하지 않습니다."}

# ✅ **📌 업로드된 파일 다운로드 API**
@app.get("/download-file/{filename}/", summary="파일 다운로드", description="업로드된 ZIP 파일을 다운로드합니다.")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/zip")
    return {"error": "파일을 찾을 수 없습니다."}

# ✅ **📌 캐릭터 데이터 API**
@app.get("/characters/", summary="캐릭터 목록 조회", description="저장된 모든 캐릭터 정보를 반환합니다.")
def read_characters(db: Session = Depends(get_db)):
    return db.query(models.Character).all()

@app.post("/characters/", summary="캐릭터 생성", description="새로운 캐릭터 데이터를 추가합니다.")
def create_character(name: str, species: str, ability: str, attack_power: int, defense_power: int, battle_style: str, speech_pattern: str, db: Session = Depends(get_db)):
    new_character = models.Character(
        name=name, species=species, ability=ability, attack_power=attack_power,
        defense_power=defense_power, battle_style=battle_style, speech_pattern=speech_pattern
    )
    db.add(new_character)
    db.commit()
    db.refresh(new_character)
    return new_character

# ✅ **📌 종족 데이터 API**
@app.get("/species/", summary="종족 목록 조회", description="저장된 모든 종족 정보를 반환합니다.")
def read_species(db: Session = Depends(get_db)):
    return db.query(models.Species).all()

@app.post("/species/", summary="새로운 종족 생성", description="새로운 종족 데이터를 추가합니다.")
def create_species(name: str, description: str, abilities: str, db: Session = Depends(get_db)):
    new_species = models.Species(name=name, description=description, abilities=abilities)
    db.add(new_species)
    db.commit()
    db.refresh(new_species)
    return new_species

# ✅ **📌 GPT 연동용 검색 API**
@app.get("/search/", summary="데이터 검색", description="입력된 키워드로 DB에서 관련 데이터를 검색합니다.")
def search_data(query: str, db: Session = Depends(get_db)):
    characters = db.query(models.Character).filter(models.Character.name.contains(query)).all()
    species = db.query(models.Species).filter(models.Species.name.contains(query)).all()
    factions = db.query(models.Faction).filter(models.Faction.name.contains(query)).all()
    technologies = db.query(models.Technology).filter(models.Technology.name.contains(query)).all()
    events = db.query(models.HistoricalEvent).filter(models.HistoricalEvent.name.contains(query)).all()

    return {
        "characters": characters,
        "species": species,
        "factions": factions,
        "technologies": technologies,
        "historical_events": events
    }

# ✅ **📌 GPT를 활용한 종족 자동 생성 API**
@app.post("/expand/species/gpt/", summary="GPT 기반 종족 생성", description="GPT-4를 활용하여 새로운 종족을 자동으로 생성하는 기능입니다.")
def expand_species_with_gpt():
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 DTP 세계관 확장을 위한 질문을 생성하는 AI입니다."},
            {"role": "user", "content": "새로운 종족을 추가하려면 어떤 질문을 해야 할까요?"}
        ]
    )
    return response
