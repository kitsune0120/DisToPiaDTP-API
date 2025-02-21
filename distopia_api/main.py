import os
import shutil
import time
import logging
import random
import io
import zipfile
import re  # 파일명 안전 처리를 위해 추가
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
import jwt

# (선택) 동영상 프레임 추출
import ffmpeg

# (선택) 문서 파싱 라이브러리
import PyPDF2
import docx

# (선택) 이미지 캡션/객체 감지용 라이브러리
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from transformers import DetrImageProcessor, DetrForObjectDetection
from PIL import Image

# (선택) LangChain Community (벡터 검색 / LLM 연동)
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain

# -------------------------------
# 1) .env 파일 로드 및 환경 변수 설정
# -------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")

if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다.")
if not DATABASE_URL:
    raise HTTPException(status_code=500, detail="❌ DATABASE_URL이 설정되지 않았습니다.")

# -------------------------------
# 로깅 설정
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# -------------------------------
# FastAPI 앱 생성
# -------------------------------
app = FastAPI(
    title="DisToPia API (Local)",
    description="DTP 세계관 API (로컬 DB + AI + 파일 관리)",
    version="4.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------
# OAuth2 (JWT) 설정
# -------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login-for-access-token")

class User(BaseModel):
    username: str
    password: str

fake_users_db = {
    "johndoe": {"username": "johndoe", "password": "secret"}
}

def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

async def optional_verify_token(authorization: str = Header(None)):
    if authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            username = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            return {"sub": username}
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        return {"sub": "anonymous"}

@app.post("/login-for-access-token")
def login_for_access_token(user: User):
    if user.username in fake_users_db and fake_users_db[user.username]["password"] == user.password:
        token = create_access_token({"sub": user.username})
        return {"access_token": token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

# -------------------------------
# DB 연결 (로컬 PostgreSQL)
# -------------------------------
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("✅ 데이터베이스에 성공적으로 연결되었습니다!")
        return conn
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return None

# -------------------------------
# DB 테이블 생성 (dtp_data, conversation)
# -------------------------------
@app.get("/create-table")
def create_table():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dtp_data (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "✅ 테이블 생성 완료!"}

# -------------------------------
# (선택) ChromaDB (RAG) 세팅
# -------------------------------
def get_chroma_client():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(collection_name="distopia_collection", persist_directory="chroma_db", embedding_function=embeddings)
    return vectordb

# -------------------------------
# 파일명 안전 처리
# -------------------------------
def secure_filename(filename: str) -> str:
    filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
    return filename

# -------------------------------
# 파일 분석 (ZIP, PDF, DOCX, 이미지 등)
# -------------------------------
def analyze_file_content(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext == ".pdf":
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
                return text if text else "PDF에서 텍스트 추출 실패"
        elif ext == ".docx":
            import docx
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text if text else "DOCX에서 텍스트 추출 실패"
        elif ext in [".png", ".jpg", ".jpeg"]:
            # 이미지 캡션 모델 로딩 (필요 시)
            return "이미지 파일 처리 (캡션 생성 등) - 필요 시 구현"
        else:
            return f"지원하지 않는 파일 형식({ext})"
    except Exception as e:
        return f"파일 분석 중 오류: {e}"

# -------------------------------
# 대화 캐시 조회/저장 (DB)
# -------------------------------
def get_cached_conversation(question: str) -> str:
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT answer FROM conversation WHERE question = %s ORDER BY created_at DESC LIMIT 1", (question,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return result[0]
        return None
    except Exception as e:
        return None

def save_conversation(question: str, answer: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        created_at = datetime.utcnow()
        cursor.execute("INSERT INTO conversation (question, answer, created_at) VALUES (%s, %s, %s)", (question, answer, created_at))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()

# -------------------------------
# 루트
# -------------------------------
@app.get("/")
def root():
    return {"message": "Hello from DTP (Local)!"}

# -------------------------------
# 예시 DB API
# -------------------------------
@app.post("/add-data")
def add_data(name: str, description: str, user: dict = Depends(optional_verify_token)):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO dtp_data (name, description) VALUES (%s, %s)", (name, description))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": f"데이터 추가 성공 (name={name})"}

@app.get("/get-data")
def get_data():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dtp_data;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"data": rows}

# -------------------------------
# 파일 업로드
# -------------------------------
from fastapi import File, UploadFile

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    safe_filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # 필요 시 파일 분석 & DB 저장
    content = analyze_file_content(file_path)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO dtp_data (name, description) VALUES (%s, %s)", (safe_filename, content))
    conn.commit()
    cursor.close()
    conn.close()
    return {"filename": safe_filename, "message": "파일 업로드 및 분석 성공"}

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, secure_filename(filename))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

@app.delete("/delete-file/{filename}")
def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, secure_filename(filename))
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"message": f"{filename} 파일 삭제 완료!"}
    else:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

# -------------------------------
# 예시 대화 API
# -------------------------------
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    history: List[str] = []

@app.post("/chat")
def chat(request: ChatRequest):
    # 예시 GPT 연동
    # vectordb = get_chroma_client()  # 필요 시 사용
    # ...
    # 여기서는 간단히 DB 캐시만 예시
    cached_answer = get_cached_conversation(request.query)
    if cached_answer:
        return {"response": cached_answer}
    answer = f"'{request.query}' 에 대한 임시 응답"  # 실제 GPT API 호출 가능
    save_conversation(request.query, answer)
    return {"response": answer}

# -------------------------------
# 로컬 실행
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
