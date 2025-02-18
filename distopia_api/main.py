import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import openai
from dotenv import load_dotenv  # ✅ 환경 변수 로드

# LangChain & ChromaDB
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

# ✅ 환경 변수 불러오기
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다. `.env` 파일을 확인하세요.")

# ✅ DB 초기화
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
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(collection_name="distopia_collection", persist_directory="chroma_db", embedding_function=embeddings)
    return vectordb

# =============================================================================
# ✅ 데이터베이스 세션 관리 개선
# =============================================================================
def get_db_safe():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# ✅ FastAPI API 엔드포인트
# =============================================================================
@app.get("/search/")
def search_data(query: str, db: Session = Depends(get_db_safe)):
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

@app.post("/chat/")
def chat_with_gpt(question: str, db: Session = Depends(get_db_safe)):
    vectordb = get_chroma_client()
    rag_chain = ConversationalRetrievalChain.from_llm(ChatOpenAI(model_name="gpt-4", openai_api_key=OPENAI_API_KEY), vectordb.as_retriever())
    
    result = rag_chain.run({"question": question})
    return {"response": result}

@app.get("/stats/")
def get_data_stats(db: Session = Depends(get_db_safe)):
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
    port = int(os.getenv("PORT", 8000))  # ✅ Render 호환성 개선
    uvicorn.run(app, host="0.0.0.0", port=port, workers=4, keepalive=10)
