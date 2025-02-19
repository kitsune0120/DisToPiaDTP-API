import os
import shutil
import time
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv
from pydantic import BaseModel

# LangChain Community 버전 (벡터 검색 / LLM 연동)
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain

# PostgreSQL 연동
import psycopg2

# =============================================================================
# 1) .env 파일 로드 & 환경 변수 체크
# =============================================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다.")

if not DATABASE_URL:
    raise HTTPException(status_code=500, detail="❌ DATABASE_URL이 설정되지 않았습니다.")

# =============================================================================
# 2) FastAPI 앱 설정
# =============================================================================
app = FastAPI(
    title="DisToPia API",
    description="DTP 세계관 API (DB + AI + RAG + 파일 관리 + ChatGPT 플러그인)",
    version="4.0"
)

# 업로드 디렉토리 생성
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =============================================================================
# 3) ChromaDB (RAG) 세팅
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
# 4) PostgreSQL 연결 함수
# =============================================================================
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print("❌ 데이터베이스 연결 실패:", e)
        return None

# =============================================================================
# 5) 기본 라우트 (테스트용)
# =============================================================================
@app.get("/")
def root():
    return {"message": "Hello from DTP!"}

# =============================================================================
# 6) DB 테이블 생성
# =============================================================================
@app.get("/create-table")
def create_table():
    conn = get_db_connection()
    if not conn:
        return {"error": "DB 연결 실패"}
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dtp_data (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "✅ dtp_data 테이블 생성 완료!"}

# =============================================================================
# 7) DB 데이터 추가
# =============================================================================
@app.post("/add-data")
def add_data(name: str, description: str):
    conn = get_db_connection()
    if not conn:
        return {"error": "DB 연결 실패"}
    cursor = conn.cursor()
    cursor.execute("INSERT INTO dtp_data (name, description) VALUES (%s, %s)", (name, description))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": f"✅ 데이터 추가 성공! (name={name}, description={description})"}

# =============================================================================
# 8) DB 데이터 조회
# =============================================================================
@app.get("/get-data")
def get_data():
    conn = get_db_connection()
    if not conn:
        return {"error": "DB 연결 실패"}
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dtp_data;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"data": rows}

# =============================================================================
# 9) 파일 업로드 API
# =============================================================================
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1].lower()
    allowed_extensions = ["zip", "png", "jpg", "jpeg", "mp4", "avi"]
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    # 동일한 파일명이 존재하면 타임스탬프 붙여서 고유화
    if os.path.exists(file_path):
        base, extension = os.path.splitext(file.filename)
        new_filename = f"{base}_{int(time.time())}{extension}"
        file_path = os.path.join(UPLOAD_DIR, new_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": file.filename, "message": "파일 업로드 성공!"}

# =============================================================================
# 10) 파일 다운로드 API
# =============================================================================
@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

# =============================================================================
# 11) RAG 기반 대화 API
# =============================================================================
@app.post("/chat")
def chat(query: str, history: list = Query(default=[])):
    """
    LangChain Community + ChromaDB + OpenAI API를 사용한 RAG 기반 대화.
    history는 대화 이력을 리스트 형태로 전달 (예: ["안녕", "안녕하세요!"])
    """
    vectordb = get_chroma_client()
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    llm = ChatOpenAI(temperature=0.7, openai_api_key=OPENAI_API_KEY)
    chain = ConversationalRetrievalChain.from_llm(llm, retriever)

    # chain에 question과 기존 대화(history)를 넣어 답변 생성
    result = chain({"question": query, "chat_history": history})
    return {"response": result["answer"]}
