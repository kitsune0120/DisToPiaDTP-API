import os
import shutil
import time
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from fastapi.openapi.utils import get_openapi

# 1) .env 파일 로드 & OPENAI_API_KEY 설정
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다.")

# 2) FastAPI 설정
app = FastAPI(
    title="DisToPia API",
    description="DTP 세계관 API (DB + AI + RAG + 파일 관리 + ChatGPT 플러그인)",
    version="4.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =============================================================================
# ✅ 기본 경로 (테스트용) - "Hello from DTP!" 로 변경
# =============================================================================
@app.get("/")
def root():
    return {"message": "Hello from DTP!"}

# =============================================================================
# ✅ ChromaDB 벡터 검색 (RAG)
# =============================================================================
def get_chroma_client():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(
        collection_name="distopia_collection",
        persist_directory="chroma_db",
        embedding_function=embeddings
    )
    return vectordb

# =============================================================================
# ✅ 파일 업로드 & 다운로드 API
# =============================================================================
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1].lower()
    allowed_extensions = ["zip", "png", "jpg", "jpeg", "mp4", "avi"]
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    # 동일한 파일명이 존재하면 타임스탬프를 붙여서 고유화
    if os.path.exists(file_path):
        base, extension = os.path.spl
