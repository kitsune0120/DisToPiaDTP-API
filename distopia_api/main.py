import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import openai

# LangChain & ChromaDB
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DisToPia API",
    description="DTP 세계관 API (DB + AI + RAG + 파일 관리)",
    version="4.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

session_storage = {}

# =============================================================================
# ✅ ChromaDB 벡터 검색 (RAG)
# =============================================================================
def get_chroma_client():
    api_key = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY)
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=api_key)
    vectordb = Chroma(collection_name="distopia_collection", persist_directory="chroma_db", embedding_function=embeddings)
    return vectordb

# =============================================================================
# ✅ 파일 업로드 & 다운로드 (ZIP, 이미지, 영상)
# =============================================================================
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    allowed_extensions = ["zip", "png", "jpg", "jpeg", "mp4", "avi"]
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ 업로드 완료"}

@app.get("/files/")
def list_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 없습니다."}

@app.get("/download/{filename}/")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    return {"error": "파일을 찾을 수 없습니다."}

# =============================================================================
# ✅ DB 데이터 조회 (JSON, Markdown, HTML)
# =============================================================================
@app.get("/all-data/")
def get_all_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    data = {
        "characters": [{"name": c.name, "species": c.species} for c in characters],
        "species": [{"name": s.name, "description": s.description} for s in species],
        "regions": [{"name": r.name, "description": r.description} for r in regions]
    }
    return data

@app.get("/visual-data/", response_class=HTMLResponse)
def get_visual_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    html = "<html><head><title>저장된 데이터</title></head><body><h1>📜 저장된 데이터</h1>"

    html += "<h2>🏅 캐릭터 목록</h2>"
    for c in characters:
        html += f"<p><strong>{c.name}</strong> ({c.species})</p>"

    html += "<h2>🦊 종족 목록</h2>"
    for s in species:
        html += f"<p><strong>{s.name}</strong> - {s.description}</p>"

    html += "<h2>🌍 지역 목록</h2>"
    for r in regions:
        html += f"<p><strong>{r.name}</strong> - {r.description}</p>"

    html += "</body></html>"
    return html

# =============================================================================
# ✅ 검색 API (AI 지원)
# =============================================================================
@app.get("/search/")
def search_data(query: str, db: Session = Depends(get_db)):
    response = ""
    
    characters = db.query(models.Character).filter(models.Character.name.contains(query)).all()
    if characters:
        response += "📌 캐릭터 정보:\n" + "".join(f"- {c.name} ({c.species})\n" for c in characters)
    
    species = db.query(models.Species).filter(models.Species.name.contains(query)).all()
    if species:
        response += "📌 종족 정보:\n" + "".join(f"- {s.name}: {s.description}\n" for s in species)
    
    regions = db.query(models.Region).filter(models.Region.name.contains(query)).all()
    if regions:
        response += "📌 지역 정보:\n" + "".join(f"- {r.name}: {r.description}\n" for r in regions)
    
    return {"message": response if response else "❌ 관련 정보 없음"}

# =============================================================================
# ✅ AI 기반 대화 (GPT + RAG)
# =============================================================================
@app.post("/chat/")
def chat_with_gpt(question: str, db: Session = Depends(get_db)):
    vectordb = get_chroma_client()
    rag_chain = ConversationalRetrievalChain.from_llm(ChatOpenAI(model_name="gpt-4", openai_api_key=OPENAI_API_KEY), vectordb.as_retriever())
    
    result = rag_chain.run({"question": question})
    return {"response": result}

# =============================================================================
# ✅ 데이터 개수 및 최근 업데이트 확인
# =============================================================================
@app.get("/stats/")
def get_data_stats(db: Session = Depends(get_db)):
    char_count = db.query(models.Character).count()
    species_count = db.query(models.Species).count()
    region_count = db.query(models.Region).count()
    latest = db.query(models.Character.updated_at).order_by(models.Character.updated_at.desc()).first()
    latest_update_time = latest[0] if latest else "데이터 없음"
    
    return {
        "characters": char_count,
        "species": species_count,
        "regions": region_count,
        "last_update": latest_update_time
    }

# =============================================================================
# ✅ FastAPI 실행 (로컬 & Render 배포 지원)
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
