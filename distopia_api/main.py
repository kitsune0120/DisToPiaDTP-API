# distopia_api/main.py

import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
import openai

# langchain_community & langchain
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
# 아직 langchain_community에 ConversationalRetrievalChain이 없으므로:
from langchain.chains import ConversationalRetrievalChain

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distopia_api.database import engine, Base, get_db
from distopia_api.models import models  # 여기서 models.Character, .Species, .Region 사용

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DTP 세계 확장 API (DB + RAG + 세션)",
    description="이 API는 DisToPia 세계관을 확장하기 위한 모든 기능을 제공합니다.",
    version="3.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 세션 기반 대화 (임시). 실제 서버 환경에선 Redis 등 권장
session_storage = {}

# =============================================================================
# A) Chroma 벡터 DB 초기화 (RAG용)
# =============================================================================
def get_chroma_client():
    api_key = os.environ.get("OPENAI_API_KEY", OPENAI_API_KEY)
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        openai_api_key=api_key
    )
    vectordb = Chroma(
        collection_name="distopia_collection",
        persist_directory="chroma_db",
        embedding_function=embeddings
    )
    return vectordb

# =============================================================================
# 1. ZIP 파일 업로드/다운로드
# =============================================================================
@app.post("/upload-zip/")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="ZIP 파일만 업로드할 수 있습니다.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ ZIP 파일 업로드 완료"}

@app.get("/uploaded-files/")
def list_uploaded_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"uploaded_files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 없습니다."}

@app.get("/download-file/{filename}/")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/zip")
    return {"error": "파일을 찾을 수 없습니다."}

# =============================================================================
# 2. DB 데이터 조회 (JSON, Markdown, HTML)
# =============================================================================
@app.get("/all-data/")
def get_all_data(db: Session = Depends(get_db)):
    # Character 모델이 없으면 에러 발생 → 이제 models.py에 있으니 정상
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    data = {
        "캐릭터 목록": [
            {"이름": f"🆕 {c.name}" if c.new else c.name, "종족": c.species} for c in characters
        ],
        "종족 목록": [
            {"이름": f"🆕 {s.name}" if s.new else s.name, "설명": s.description} for s in species
        ],
        "지역 목록": [
            {"이름": f"🆕 {r.name}" if r.new else r.name, "설명": r.description} for r in regions
        ]
    }
    return data

@app.get("/formatted-data/")
def get_formatted_data(db: Session = Depends(get_db)):
    chars = db.query(models.Character).all()
    spcs = db.query(models.Species).all()
    regs = db.query(models.Region).all()

    md = "# 📜 저장된 데이터\n\n"
    md += "## 🏅 캐릭터 목록\n"
    for c in chars:
        prefix = "🆕 " if c.new else ""
        md += f"- **{prefix}{c.name}** ({c.species})\n"
    md += "\n## 🦊 종족 목록\n"
    for s in spcs:
        prefix = "🆕 " if s.new else ""
        md += f"- **{prefix}{s.name}**\n  - 설명: {s.description}\n\n"
    md += "## 🌍 지역 목록\n"
    for r in regs:
        prefix = "🆕 " if r.new else ""
        md += f"- **{prefix}{r.name}**\n  - 설명: {r.description}\n\n"

    return {"formatted_data": md}

@app.get("/visualized-data/", response_class=HTMLResponse)
def get_visualized_data(db: Session = Depends(get_db)):
    chars = db.query(models.Character).all()
    spcs = db.query(models.Species).all()
    regs = db.query(models.Region).all()

    html = """
    <html><head><title>저장된 데이터</title></head><body>
    <h1>📜 저장된 데이터</h1><h2>🏅 캐릭터 목록</h2>
    """
    for c in chars:
        prefix = "🆕 " if c.new else ""
        html += f"<p>{prefix}<strong>{c.name}</strong> ({c.species})</p>"
    html += "<h2>🦊 종족 목록</h2>"
    for s in spcs:
        prefix = "🆕 " if s.new else ""
        html += f"<p>{prefix}<strong>{s.name}</strong> - {s.description}</p>"
    html += "<h2>🌍 지역 목록</h2>"
    for r in regs:
        prefix = "🆕 " if r.new else ""
        html += f"<p>{prefix}<strong>{r.name}</strong> - {r.description}</p>"
    html += "</body></html>"

    return html

# =============================================================================
# 3. NEW! 데이터 정리
# =============================================================================
@app.post("/confirm-view/")
def confirm_view(db: Session = Depends(get_db)):
    db.query(models.Character).filter(models.Character.new == True).update({"new": False})
    db.query(models.Species).filter(models.Species.new == True).update({"new": False})
    db.query(models.Region).filter(models.Region.new == True).update({"new": False})
    db.commit()
    return {"message": "✅ 새로운 데이터 정리 완료"}

# =============================================================================
# 4. GPT가 기억하는 데이터 저장
# =============================================================================
@app.post("/remember/")
def remember_data(category: str, name: str, description: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }
    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리 (character/species/region)")

    existing = db.query(model_map[category]).filter(model_map[category].name == name).first()
    if existing:
        existing.description = description
        db.commit()
        db.refresh(existing)
        return {"message": f"✅ 기존 {category} '{name}' 업데이트 완료"}
    else:
        new_item = model_map[category](name=name, description=description, new=True)
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return {"message": f"✅ 새로운 {category} '{name}'이(가) 저장됨"}

# =============================================================================
# 5. DisToPia 세계관 채팅
# =============================================================================
@app.post("/dtp-chat/")
def dtp_chat(question: str, db: Session = Depends(get_db)):
    response = ""

    chars = db.query(models.Character).filter(models.Character.name.contains(question)).all()
    if chars:
        response += "📌 캐릭터 정보:\n"
        for c in chars:
            response += f"- {c.name} ({c.species})\n"

    spcs = db.query(models.Species).filter(models.Species.name.contains(question)).all()
    if spcs:
        response += "📌 종족 정보:\n"
        for s in spcs:
            response += f"- {s.name}\n  설명: {s.description}\n"

    regs = db.query(models.Region).filter(models.Region.name.contains(question)).all()
    if regs:
        response += "📌 지역 정보:\n"
        for r in regs:
            response += f"- {r.name}\n  설명: {r.description}\n"

    if not response:
        response = "❌ 해당 정보가 없습니다. '기억해줘'로 추가할 수 있음."

    return {"message": response}

# =============================================================================
# 6. 데이터 개수 및 최근 업데이트
# =============================================================================
@app.get("/data-info/")
def get_data_info(db: Session = Depends(get_db)):
    char_count = db.query(models.Character).count()
    species_count = db.query(models.Species).count()
    region_count = db.query(models.Region).count()

    # 만약 Character 모델에 updated_at 칼럼이 없다면, None일 수도 있음
    latest = db.query(models.Character.updated_at).order_by(models.Character.updated_at.desc()).first()
    latest_update_time = latest[0] if latest else "데이터 없음"

    return {
        "캐릭터 개수": char_count,
        "종족 개수": species_count,
        "지역 개수": region_count,
        "최근 업데이트 시간": latest_update_time
    }

# =============================================================================
# 7. 검색 기능
# =============================================================================
@app.get("/search-dat
