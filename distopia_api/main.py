import os
import shutil
import time
import logging
import zipfile
import re
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
import jwt
import openai  # GPT-4 호출을 위한 라이브러리
from typing import List

# (선택) 동영상 프레임 추출 (ffmpeg-python)
import ffmpeg

# (선택) 문서 파싱 라이브러리
import PyPDF2
import docx

# (선택) 이미지 캡션/객체 감지용 라이브러리 (transformers, pillow, torch)
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from transformers import DetrImageProcessor, DetrForObjectDetection
from PIL import Image

# (선택) LangChain Community (벡터 검색 / LLM 연동)
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain

# .env 파일 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")  # JWT 발급용 비밀키

if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다.")
if not DATABASE_URL:
    raise HTTPException(status_code=500, detail="❌ DATABASE_URL이 설정되지 않았습니다.")

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
from fastapi.middleware.cors import CORSMiddleware  # CORS 미들웨어 임포트

app = FastAPI(
    title="DisToPia API (Local)",
    description="DTP 세계관 API (로컬 DB + AI + 파일 관리)",
    version="4.0"
)

# CORS 설정: 127.0.0.1에서의 요청을 허용
origins = [
    "https://127.0.0.1",  # 원하는 오리진을 추가
    "http://127.0.0.1",   # 포트 없이도 허용
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 허용할 오리진 설정
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# Custom OpenAPI (servers 항목 포함, HTTPS 적용)
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.1.0"
    openapi_schema["servers"] = [
        {"url": "https://127.0.0.1:8001", "description": "Local development server"}
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# OAuth2 (JWT) 설정
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

# GPT-4 응답 처리
openai.api_key = OPENAI_API_KEY

def get_gpt_response(query: str):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": query}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"❌ GPT-4 호출 실패: {e}")
        return "GPT-4 모델 호출 중 오류가 발생했습니다."

# DB 연결 (로컬 PostgreSQL)
def get_db_connection():
    logger.info("🔍 DB 연결 시도 중...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("✅ 데이터베이스에 성공적으로 연결되었습니다!")
        return conn
    except Exception as e:
        logger.error(f"❌ DB 연결 실패: {e}")
        return None

# DB 테이블 생성 (dtp_data, conversation)
@app.get("/create-table")
def create_table():
    logger.info("GET /create-table 요청 받음.")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS dtp_data (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT
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

# 파일 업로드 및 카테고리별 분류
CATEGORY_KEYWORDS = {
    "포타토": "포타토관련",
    "꽃삐": "꽃삐관련",
    "지역": "지역관련"
}

def categorize_file_content(file_content: str) -> str:
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in file_content:
            return category
    return "기타"  # 키워드가 없다면 기타로 분류

@app.post("/upload-zip/")
async def upload_zip(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(UPLOAD_DIR)
        
        for extracted_file in zip_ref.namelist():
            extracted_file_path = os.path.join(UPLOAD_DIR, extracted_file)
            with open(extracted_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                category = categorize_file_content(file_content)
                save_to_db(extracted_file, file_content, category)
        
        return {"message": "Zip 파일 업로드 및 분석 완료"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 에러 발생: {e}")

def save_to_db(filename: str, content: str, category: str):
    # 실제 DB에 저장하는 코드
    logger.info(f"파일명: {filename}, 카테고리: {category}, 내용: {content[:100]}...")  # 내용 일부만 출력
    # 여기에 DB 저장 로직 추가 (예: INSERT INTO 테이블)

# 카테고리별 데이터 조회
@app.get("/get-category/{category_name}")
def get_category_data(category_name: str):
    data = get_category_from_db(category_name)
    return {"category": category_name, "data": data}

def get_category_from_db(category_name: str):
    # 실제 DB에서 카테고리별 데이터 가져오는 코드 추가
    return [
        {"filename": "potato_file1.txt", "content": "포타토 관련 내용..."},
        {"filename": "potato_file2.txt", "content": "또 다른 포타토 관련 내용..."}
    ]

# Flask와 비슷한 FastAPI 구조로 라우트 설정
@app.get("/")
def hello_world():
    return {"message": "Hello, World!"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
