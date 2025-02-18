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

# ✅ **📌 캐릭터 데이터 생성 또는 업데이트 API**
@app.post("/characters/", summary="캐릭터 생성 또는 업데이트", description="중복된 캐릭터가 있으면 업데이트하고, 없으면 새로 추가합니다.")
def create_or_update_character(name: str, species: str, ability: str, attack_power: int, defense_power: int, battle_style: str, speech_pattern: str, db: Session = Depends(get_db)):
    existing_character = db.query(models.Character).filter(models.Character.name == name).first()

    if existing_character:
        existing_character.species = species
        existing_character.ability = ability
        existing_character.attack_power = attack_power
        existing_character.defense_power = defense_power
        existing_character.battle_style = battle_style
        existing_character.speech_pattern = speech_pattern
        db.commit()
        db.refresh(existing_character)
        return {"message": "✅ 기존 캐릭터 정보가 업데이트되었습니다.", "character": existing_character}

    new_character = models.Character(
        name=name, species=species, ability=ability, attack_power=attack_power,
        defense_power=defense_power, battle_style=battle_style, speech_pattern=speech_pattern
    )
    db.add(new_character)
    db.commit()
    db.refresh(new_character)
    return {"message": "✅ 새로운 캐릭터가 추가되었습니다.", "character": new_character}

# ✅ **📌 종족 데이터 생성 또는 업데이트 API**
@app.post("/species/", summary="종족 생성 또는 업데이트", description="중복된 종족이 있으면 업데이트하고, 없으면 새로 추가합니다.")
def create_or_update_species(name: str, description: str, abilities: str, db: Session = Depends(get_db)):
    existing_species = db.query(models.Species).filter(models.Species.name == name).first()

    if existing_species:
        existing_species.description = description
        existing_species.abilities = abilities
        db.commit()
        db.refresh(existing_species)
        return {"message": "✅ 기존 종족 정보가 업데이트되었습니다.", "species": existing_species}

    new_species = models.Species(name=name, description=description, abilities=abilities)
    db.add(new_species)
    db.commit()
    db.refresh(new_species)
    return {"message": "✅ 새로운 종족이 추가되었습니다.", "species": new_species}

# ✅ **📌 GPT 기반 종족 데이터 생성 또는 업데이트 API**
@app.post("/expand/species/gpt/", summary="GPT 기반 종족 생성 또는 업데이트", description="GPT-4를 활용하여 새로운 종족 데이터를 생성합니다.")
def expand_species_with_gpt():
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 DTP 세계관 확장을 위한 질문을 생성하는 AI입니다."},
            {"role": "user", "content": "새로운 종족을 추가하려면 어떤 질문을 해야 할까요?"}
        ]
    )
    species_data = response['choices'][0]['message']['content']

    existing_species = db.query(models.Species).filter(models.Species.name == species_data["name"]).first()

    if existing_species:
        existing_species.description = species_data["description"]
        existing_species.abilities = species_data["abilities"]
        db.commit()
        db.refresh(existing_species)
        return {"message": "✅ 기존 종족 정보가 업데이트되었습니다.", "species": existing_species}

    new_species = models.Species(name=species_data["name"], description=species_data["description"], abilities=species_data["abilities"])
    db.add(new_species)
    db.commit()
    db.refresh(new_species)
    return {"message": "✅ 새로운 종족이 추가되었습니다.", "species": new_species}

# ✅ **🚀 자동 포트 설정 (Render 환경 호환)**
import uvicorn

PORT = int(os.environ.get("PORT", 8000))  # Render에서 제공하는 포트 사용
uvicorn.run(app, host="0.0.0.0", port=PORT)
