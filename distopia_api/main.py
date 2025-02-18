import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import openai

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DTP 세계 확장 API",
    description="이 API는 DTP 세계관을 확장하는 기능을 제공합니다.",
    version="1.5"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ **📌 데이터 개수 및 최근 업데이트 시간 확인 (`GET /data-info/`)**
@app.get("/data-info/", summary="데이터 개수 및 최근 업데이트 시간 확인")
def get_data_info(db: Session = Depends(get_db)):
    char_count = db.query(models.Character).count()
    species_count = db.query(models.Species).count()
    region_count = db.query(models.Region).count()

    latest_update = db.query(models.Character.updated_at).order_by(models.Character.updated_at.desc()).first()
    latest_update_time = latest_update[0] if latest_update else "데이터 없음"

    return {
        "캐릭터 개수": char_count,
        "종족 개수": species_count,
        "지역 개수": region_count,
        "최근 업데이트 시간": latest_update_time
    }

# ✅ **📌 검색 기능 (`GET /search-data/`)**
@app.get("/search-data/", summary="데이터 검색", description="입력된 키워드로 저장된 데이터를 검색합니다.")
def search_data(query: str, db: Session = Depends(get_db)):
    characters = db.query(models.Character).filter(models.Character.name.contains(query)).all()
    species = db.query(models.Species).filter(models.Species.name.contains(query)).all()
    regions = db.query(models.Region).filter(models.Region.name.contains(query)).all()

    return {
        "검색된 캐릭터": [{"이름": char.name, "종족": char.species, "능력": char.ability} for char in characters],
        "검색된 종족": [{"이름": spec.name, "설명": spec.description, "능력": spec.abilities} for spec in species],
        "검색된 지역": [{"이름": reg.name, "설명": reg.description, "기후": reg.climate} for reg in regions]
    }

# ✅ **📌 특정 데이터 삭제 기능 (`DELETE /delete-data/{category}/{name}/`)**
@app.delete("/delete-data/{category}/{name}/", summary="특정 데이터 삭제", description="캐릭터, 종족, 지역 등 특정 데이터를 삭제합니다.")
def delete_data(category: str, name: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리. 'character', 'species', 'region' 중 선택하세요.")

    deleted_item = db.query(model_map[category]).filter(model_map[category].name == name).first()
    if not deleted_item:
        raise HTTPException(status_code=404, detail=f"{category}에서 '{name}'을(를) 찾을 수 없습니다.")

    db.delete(deleted_item)
    db.commit()
    return {"message": f"✅ {category}에서 '{name}'이(가) 삭제되었습니다."}

# ✅ **📌 GPT가 "기억해줘" 하면 자동으로 데이터베이스에 저장 (`POST /remember/`)**
@app.post("/remember/", summary="GPT가 기억하는 데이터 저장", description="GPT의 데이터를 DB에 자동 저장합니다.")
def remember_data(category: str, name: str, description: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리. 'character', 'species', 'region' 중 선택하세요.")

    existing_item = db.query(model_map[category]).filter(model_map[category].name == name).first()

    if existing_item:
        existing_item.description = description  # 기존 데이터 업데이트
        db.commit()
        db.refresh(existing_item)
        return {"message": f"✅ 기존 {category} '{name}' 정보가 업데이트되었습니다."}

    new_item = model_map[category](name=name, description=description)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return {"message": f"✅ 새로운 {category} '{name}'이(가) 저장되었습니다."}

# ✅ **📌 DisToPia 세계관 카테고리 채팅은 데이터베이스 내에서만 답변 (`POST /dtp-chat/`)**
@app.post("/dtp-chat/", summary="DisToPia 세계관 내 질문", description="질문에 대한 답변을 데이터베이스에서 검색 후 반환합니다.")
def dtp_chat(question: str, db: Session = Depends(get_db)):  # ✅ 오류 수정: 괄호 닫힘 문제 해결
    response = ""

    # ✅ 캐릭터 데이터 검색
    characters = db.query(models.Character).filter(models.Character.name.contains(question)).all()
    if characters:
        response += "📌 캐릭터 정보:\n"
        for char in characters:
            response += f"- {char.name} ({char.species})\n  능력: {char.ability}\n  공격력: {char.attack_power}, 방어력: {char.defense_power}\n\n"

    # ✅ 종족 데이터 검색
    species = db.query(models.Species).filter(models.Species.name.contains(question)).all()
    if species:
        response += "📌 종족 정보:\n"
        for spec in species:
            response += f"- {spec.name}\n  설명: {spec.description}\n  능력: {spec.abilities}\n\n"

    # ✅ 지역 데이터 검색
    regions = db.query(models.Region).filter(models.Region.name.contains(question)).all()
    if regions:
        response += "📌 지역 정보:\n"
        for reg in regions:
            response += f"- {reg.name}\n  설명: {reg.description}\n  기후: {reg.climate}\n\n"

    if not response:
        response = "❌ 해당 정보가 데이터베이스에 없습니다. 새로운 정보를 추가하려면 '기억해줘' 기능을 사용하세요."

    return {"message": response}

import uvicorn

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
