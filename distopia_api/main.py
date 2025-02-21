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

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Request, Body, Query
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
import jwt

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

# -------------------------------
# 1) .env 파일 로드 및 환경 변수 설정
# -------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")  # JWT 발급용 비밀키

# 디버그: 환경 변수 출력
print(f"📌 현재 설정된 OPENAI_API_KEY: {OPENAI_API_KEY}")
print(f"📌 현재 설정된 DATABASE_URL: {DATABASE_URL}")

if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다.")
if not DATABASE_URL:
    raise HTTPException(status_code=500, detail="❌ DATABASE_URL이 설정되지 않았습니다.")

# -------------------------------
# 로깅 설정
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -------------------------------
# Custom OpenAPI (servers 항목)
# -------------------------------
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="DisToPia API (Local)",
        version="4.0",
        description="DTP 세계관 API (로컬 DB + AI + 파일 관리)",
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.1.0"
    # 서버 주소를 http://127.0.0.1:8000 으로 설정 (FastAPI docs 기준)
    openapi_schema["servers"] = [
        {"url": "http://127.0.0.1:8000", "description": "Local development server"}
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# -------------------------------
# FastAPI 앱 생성
# -------------------------------
app = FastAPI(
    title="DisToPia API (Local)",
    description="DTP 세계관 API (로컬 DB + AI + 파일 관리)",
    version="4.0"
)
app.openapi = custom_openapi

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

# 기존 인증 의존성을 "옵셔널 인증"으로 변경
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
# DB 연결 (로컬 PostgreSQL) - 디버그 로그 포함
# -------------------------------
def get_db_connection():
    logger.info("🔍 get_db_connection() 호출됨.")
    try:
        logger.info("🔍 DB 연결 시도 중...")
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("✅ 데이터베이스에 성공적으로 연결되었습니다!")
        return conn
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}", exc_info=True)
        return None

# -------------------------------
# DB 테이블 생성 (dtp_data, conversation)
# -------------------------------
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
# 파일 분석 함수들
# -------------------------------
def analyze_text_file(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[오류] 텍스트 파일 읽기 실패: {e}"

def analyze_pdf(file_path: str) -> str:
    try:
        text = ""
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"[오류] PDF 파싱 실패: {e}"

def analyze_docx(file_path: str) -> str:
    try:
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        return f"[오류] DOCX 파싱 실패: {e}"

def analyze_image(file_path: str) -> str:
    result = ""
    try:
        load_image_caption_model()
        load_object_detection_model()
        with Image.open(file_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            # 이미지 캡션 생성
            pixel_values = image_processor(img, return_tensors="pt").pixel_values
            output_ids = image_caption_model.generate(pixel_values, max_length=50, num_beams=4)
            caption = caption_tokenizer.decode(output_ids[0], skip_special_tokens=True)
            result += f"[캡션] {caption}\n"
            # 객체 감지 (간단 예시)
            inputs = object_processor(images=img, return_tensors="pt")
            outputs = object_detector(**inputs)
            detected = "객체: " + ", ".join([f"{obj}" for obj in outputs.logits.argmax(dim=-1).tolist()[0:3]])
            result += f"[객체 감지] {detected}"
    except Exception as e:
        result += f"[오류] 이미지 분석 실패: {e}"
    return result

def analyze_video(file_path: str) -> str:
    captions = []
    try:
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format']['duration'])
        num_frames = int(duration // 10)
        for i in range(num_frames):
            out_file = f"{file_path}_frame_{i}.jpg"
            (
                ffmpeg
                .input(file_path, ss=i*10)
                .output(out_file, vframes=1)
                .overwrite_output()
                .run(quiet=True)
            )
            cap = analyze_image(out_file)
            captions.append(cap)
            os.remove(out_file)
        summary = " | ".join(captions)
        return f"[동영상 요약] {summary}"
    except Exception as e:
        return f"[오류] 동영상 분석 실패: {e}"

def analyze_file_content(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".txt", ".html", ".csv", ".json", ".md", ".log", ".xml"]:
        return analyze_text_file(file_path)
    elif ext == ".pdf":
        return analyze_pdf(file_path)
    elif ext == ".docx":
        return analyze_docx(file_path)
    elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
        return analyze_image(file_path)
    elif ext in [".mp4", ".mov", ".avi", ".mkv", ".wmv"]:
        return analyze_video(file_path)
    else:
        return f"[미지원] {ext} 확장자는 현재 지원되지 않습니다."

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
# 루트 엔드포인트
# -------------------------------
@app.get("/")
def root():
    logger.info("GET / 요청 받음.")
    return {"message": "Hello from DTP (GPT Actions)!"}

# -------------------------------
# 예시 DB API
# -------------------------------
@app.post("/add-data")
def add_data(name: str, description: str, user: dict = Depends(optional_verify_token)):
    logger.info(f"POST /add-data 요청 받음. 사용자: {user['sub']}")
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
    logger.info("GET /get-data 요청 받음.")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dtp_data;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"data": rows}

@app.put("/update-data/{data_id}")
def update_data(data_id: int, name: str, description: str, user: dict = Depends(optional_verify_token)):
    logger.info(f"PUT /update-data/{data_id} 요청 받음. 사용자: {user['sub']}")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("UPDATE dtp_data SET name = %s, description = %s WHERE id = %s", (name, description, data_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": f"✅ 데이터 업데이트 완료! (id={data_id})"}

@app.delete("/delete-data/{data_id}")
def delete_data(data_id: int, user: dict = Depends(optional_verify_token)):
    logger.info(f"DELETE /delete-data/{data_id} 요청 받음. 사용자: {user['sub']}")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dtp_data WHERE id = %s", (data_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": f"✅ 데이터 삭제 완료! (id={data_id})"}

# -------------------------------
# 파일 업로드 API
# -------------------------------
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    logger.info("POST /upload/ 요청 받음.")
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        if os.path.exists(file_path):
            base, extension = os.path.splitext(file.filename)
            file_path = os.path.join(UPLOAD_DIR, f"{base}_{int(time.time())}{extension}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        content = analyze_file_content(file_path)
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="DB 연결 실패")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO dtp_data (name, description) VALUES (%s, %s)", (os.path.basename(file_path), content))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error("파일 저장 중 에러 발생: %s", e)
        raise HTTPException(status_code=500, detail=f"파일 업로드/분석에 실패했습니다: {e}")
    return {"filename": os.path.basename(file_path), "message": "파일 업로드 및 분석/DB 저장 성공"}

@app.get("/download/{filename}")
def download_file(filename: str):
    logger.info(f"GET /download/{filename} 요청 받음.")
    file_path = os.path.join(UPLOAD_DIR, secure_filename(filename))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

@app.delete("/delete-file/{filename}")
def delete_file(filename: str):
    logger.info(f"DELETE /delete-file/{filename} 요청 받음.")
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
    logger.info("POST /chat 요청 받음.")
    cached_answer = get_cached_conversation(request.query)
    if cached_answer:
        return {"response": cached_answer}
    answer = f"'{request.query}' 에 대한 임시 응답"  # 실제 GPT API 호출 가능
    save_conversation(request.query, answer)
    return {"response": answer}

# -------------------------------
# Discord 봇 통합 (플레이스홀더)
# -------------------------------
@app.get("/discord-bot")
def discord_bot_command(command: str):
    logger.info(f"GET /discord-bot 요청 받음. Command: {command}")
    return {"message": f"Discord 봇이 '{command}' 명령을 처리했습니다."}

# -------------------------------
# RP 이벤트 생성 (플레이스홀더)
# -------------------------------
@app.post("/rp-event")
def rp_event(event: str):
    logger.info(f"POST /rp-event 요청 받음. Event: {event}")
    return {"message": f"RP 이벤트 '{event}'가 생성되었습니다."}

# -------------------------------
# 게임 상태 조회 (플레이스홀더)
# -------------------------------
@app.get("/game-status")
def game_status():
    logger.info("GET /game-status 요청 받음.")
    status = {
        "players": random.randint(1, 100),
        "score": random.randint(0, 1000),
        "status": "running"
    }
    return {"game_status": status}

# -------------------------------
# 성장형 피드백
# -------------------------------
feedback_storage = {}

@app.post("/growth-feedback")
def growth_feedback(user: str, feedback: str):
    logger.info(f"POST /growth-feedback 요청 받음. 사용자: {user}, 피드백: {feedback}")
    if user in feedback_storage:
        feedback_storage[user] += " " + feedback
    else:
        feedback_storage[user] = feedback
    return {"message": "피드백이 저장되었습니다.", "feedback": feedback_storage[user]}

# -------------------------------
# 개인화 업데이트
# -------------------------------
@app.post("/update-personalization")
def update_personalization(user: str, preferences: str):
    logger.info(f"POST /update-personalization 요청 받음. 사용자: {user}, 선호도: {preferences}")
    return {"message": f"{user}님의 개인화 설정이 업데이트되었습니다.", "preferences": preferences}

# -------------------------------
# 대화 내용 백업
# -------------------------------
@app.post("/backup-memory")
def backup_memory(user_id: str, query: str, response: str):
    try:
        backup_file = os.path.join("D:/backup", "memory_logs.txt")
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        with open(backup_file, "a", encoding="utf-8") as file:
            file.write(f"{datetime.now()} - User: {user_id}, Query: {query}, Response: {response}\n")
        return {"message": "✅ 대화 내용이 백업되었습니다!"}
    except Exception as e:
        return {"error": f"백업 실패: {e}"}

# -------------------------------
# DB 백업 (자동 저장)
# -------------------------------
@app.get("/backup-db")
def backup_db():
    try:
        backup_file = os.path.join("D:/backup", "db_backup.sql")
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        conn = get_db_connection()
        if not conn:
            return {"error": "DB 연결 실패"}
        cursor = conn.cursor()
        with open(backup_file, "w", encoding="utf-8") as file:
            cursor.copy_expert("COPY dtp_data TO STDOUT WITH CSV HEADER", file)
        cursor.close()
        conn.close()
        return {"message": f"✅ 데이터베이스가 백업되었습니다! 파일: {backup_file}"}
    except Exception as e:
        return {"error": f"DB 백업 실패: {e}"}

# -------------------------------
# GPT Actions용 actions.json 엔드포인트
# -------------------------------
@app.get("/actions.json", include_in_schema=False)
def get_actions_json():
    actions_schema = {
        "version": "1.0",
        "actions": [
            {
                "name": "root",
                "description": "Basic test route",
                "endpoint": "/",
                "method": "GET",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "createTable",
                "description": "Create the dtp_data table",
                "endpoint": "/create-table",
                "method": "GET",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "addData",
                "description": "Add data to the DTP world",
                "endpoint": "/add-data",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "데이터 이름"},
                        "description": {"type": "string", "description": "데이터 설명"}
                    },
                    "required": ["name", "description"]
                }
            },
            {
                "name": "getData",
                "description": "Retrieve DTP data list",
                "endpoint": "/get-data",
                "method": "GET",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "updateData",
                "description": "Update data by ID",
                "endpoint": "/update-data/{data_id}",
                "method": "PUT",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_id": {"type": "number", "description": "업데이트할 데이터의 ID"},
                        "name": {"type": "string", "description": "새 이름"},
                        "description": {"type": "string", "description": "새 설명"}
                    },
                    "required": ["data_id", "name", "description"]
                }
            },
            {
                "name": "deleteData",
                "description": "Delete data by ID",
                "endpoint": "/delete-data/{data_id}",
                "method": "DELETE",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_id": {"type": "number", "description": "삭제할 데이터의 ID"}
                    },
                    "required": ["data_id"]
                }
            },
            {
                "name": "uploadFile",
                "description": "Upload a file",
                "endpoint": "/upload/",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "파일(이진 데이터) - multipart/form-data로 전송 필요"
                        }
                    },
                    "required": ["file"]
                }
            },
            {
                "name": "downloadFile",
                "description": "Download a file by filename",
                "endpoint": "/download/{filename}",
                "method": "GET",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "다운로드할 파일 이름"}
                    },
                    "required": ["filename"]
                }
            },
            {
                "name": "chatRAG",
                "description": "RAG 기반 대화 API",
                "endpoint": "/chat",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "사용자 질문"},
                        "history": {
                            "type": "array",
                            "description": "이전 대화 히스토리",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "generateLyrics",
                "description": "노래 가사 생성 API",
                "endpoint": "/generate-lyrics/",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "theme": {"type": "string", "description": "노래 주제"}
                    },
                    "required": ["theme"]
                }
            },
            {
                "name": "generateSong",
                "description": "노래(가사+구조) 생성 API",
                "endpoint": "/generate-song/",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "theme": {"type": "string", "description": "노래 주제"}
                    },
                    "required": ["theme"]
                }
            },
            {
                "name": "discordBotCommand",
                "description": "Discord 봇 명령 테스트",
                "endpoint": "/discord-bot",
                "method": "GET",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "봇 명령어"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "rpEvent",
                "description": "RP 이벤트 생성",
                "endpoint": "/rp-event",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string", "description": "생성할 이벤트 이름"}
                    },
                    "required": ["event"]
                }
            },
            {
                "name": "gameStatus",
                "description": "게임 상태 조회",
                "endpoint": "/game-status",
                "method": "GET",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "growthFeedback",
                "description": "사용자 피드백 저장",
                "endpoint": "/growth-feedback",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user": {"type": "string", "description": "사용자 이름"},
                        "feedback": {"type": "string", "description": "피드백 내용"}
                    },
                    "required": ["user", "feedback"]
                }
            },
            {
                "name": "updatePersonalization",
                "description": "사용자 개인화 설정 업데이트",
                "endpoint": "/update-personalization",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user": {"type": "string", "description": "사용자 이름"},
                        "preferences": {"type": "string", "description": "선호 설정 내용"}
                    },
                    "required": ["user", "preferences"]
                }
            },
            {
                "name": "backupMemory",
                "description": "대화 내용 백업",
                "endpoint": "/backup-memory",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "사용자 ID"},
                        "query": {"type": "string", "description": "사용자 입력"},
                        "response": {"type": "string", "description": "GPT 응답"}
                    },
                    "required": ["user_id", "query", "response"]
                }
            },
            {
                "name": "backupDB",
                "description": "DB 백업",
                "endpoint": "/backup-db",
                "method": "GET",
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        ]
    }
    return actions_schema

# -------------------------------
# OpenAPI 스펙 엔드포인트 (FastAPI 기본 문서)
# -------------------------------
@app.get("/openapi.json", include_in_schema=False)
def openapi_schema():
    from fastapi.openapi.utils import get_openapi
    return get_openapi(title=app.title, version=app.version, routes=app.routes)

# -------------------------------
# 앱 실행
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Render가 주는 PORT 사용, 없으면 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
