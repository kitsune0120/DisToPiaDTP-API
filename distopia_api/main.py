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
import openai  # GPT-4 호출을 위한 라이브러리

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
# FastAPI 앱 생성
# -------------------------------
app = FastAPI(
    title="DisToPia API (Local)",
    description="DTP 세계관 API (로컬 DB + AI + 파일 관리)",
    version="4.0"
)

# -------------------------------
# Custom OpenAPI (servers 항목 포함, HTTPS 적용 예시)
# -------------------------------
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
    # 서버 URL을 HTTPS로 설정하고 싶다면 아래와 같이 수정 (예: https://127.0.0.1:8000)
    # 여기서는 예시로 HTTPS를 사용하지 않고 http로 설정하는 경우입니다.
    openapi_schema["servers"] = [
        {"url": "http://127.0.0.1:8000", "description": "Local development server"}
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

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
# GPT-4 응답 처리
# -------------------------------
openai.api_key = OPENAI_API_KEY

def get_gpt_response(query: str):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query}
            ]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"❌ GPT-4 호출 실패: {e}")
        return "GPT-4 모델 호출 중 오류가 발생했습니다."

# -------------------------------
# DB 연결 (로컬 PostgreSQL)
# -------------------------------
def get_db_connection():
    logger.info("🔍 DB 연결 시도 중...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("✅ 데이터베이스에 성공적으로 연결되었습니다!")
        return conn
    except Exception as e:
        logger.error(f"❌ DB 연결 실패: {e}")
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
# ChromaDB (RAG) 세팅
# -------------------------------
def get_chroma_client():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(collection_name="distopia_collection", persist_directory="chroma_db", embedding_function=embeddings)
    return vectordb

# -------------------------------
# 파일명 안전 처리
# -------------------------------
def secure_filename(filename: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '', filename)

# -------------------------------
# 이미지 캡션 및 객체 감지 모델 로드
# -------------------------------
def load_image_caption_model():
    global image_caption_model, caption_tokenizer, image_processor
    image_caption_model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    caption_tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    image_processor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")

def load_object_detection_model():
    global object_detector, object_processor
    object_detector = DetrForObjectDetection.from_pretrained("facebook/detr-resnet-50")
    object_processor = DetrImageProcessor.from_pretrained("facebook/detr-resnet-50")

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
        return "\n".join([para.text for para in doc.paragraphs])
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
            pixel_values = image_processor(img, return_tensors="pt").pixel_values
            output_ids = image_caption_model.generate(pixel_values, max_length=50, num_beams=4)
            caption = caption_tokenizer.decode(output_ids[0], skip_special_tokens=True)
            result += f"[캡션] {caption}\n"
            inputs = object_processor(images=img, return_tensors="pt")
            outputs = object_detector(**inputs)
            detected = "객체: " + ", ".join([str(obj) for obj in outputs.logits.argmax(dim=-1).tolist()[0:3]])
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
    except Exception:
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
    except Exception:
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
class ChatRequest(BaseModel):
    query: str
    history: List[str] = []

@app.post("/chat")
def chat(request: ChatRequest):
    logger.info("POST /chat 요청 받음.")
    cached_answer = get_cached_conversation(request.query)
    if cached_answer:
        return {"response": cached_answer}
    answer = get_gpt_response(request.query)
    save_conversation(request.query, answer)
    return {"response": answer}

# -------------------------------
# Discord 봇 통합 (디스코드 봇 명령 처리)
# -------------------------------
@app.get("/discord-bot")
def discord_bot_command(command: str):
    logger.info(f"GET /discord-bot 요청 받음. Command: {command}")
    try:
        if command.lower() == "ping":
            return {"message": "Pong!"}
        else:
            return {"message": f"Discord 봇이 '{command}' 명령을 처리했습니다."}
    except Exception as e:
        return {"error": f"디스코드 봇 명령 처리 실패: {e}"}

# -------------------------------
# RP 이벤트 생성 (플레이스홀더)
# -------------------------------
@app.post("/rp-event")
def rp_event(event: str):
    logger.info(f"POST /rp-event 요청 받음. Event: {event}")
    try:
        return {"message": f"RP 이벤트 '{event}'가 생성되었습니다."}
    except Exception as e:
        return {"error": f"RP 이벤트 생성 실패: {e}"}

# -------------------------------
# 게임 상태 조회 (플레이스홀더)
# -------------------------------
@app.get("/game-status")
def game_status():
    logger.info("GET /game-status 요청 받음.")
    try:
        status = {
            "players": random.randint(1, 100),
            "score": random.randint(0, 1000),
            "status": "running"
        }
        return {"game_status": status}
    except Exception as e:
        return {"error": f"게임 상태 조회 실패: {e}"}

# -------------------------------
# 성장형 피드백
# -------------------------------
@app.post("/growth-feedback")
def growth_feedback(user: str, feedback: str):
    logger.info(f"POST /growth-feedback 요청 받음. 사용자: {user}, 피드백: {feedback}")
    global feedback_storage
    if 'feedback_storage' not in globals():
        feedback_storage = {}
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
        "openapi": "3.1.0",
        "info": {
            "title": "DisToPia API Actions",
            "version": "1.0",
            "description": "Actions schema for GPT integration"
        },
        "paths": {
            "/login-for-access-token": {
                "post": {
                    "summary": "사용자 로그인 및 JWT 토큰 발급",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {
                                            "type": "string",
                                            "description": "사용자 아이디"
                                        },
                                        "password": {
                                            "type": "string",
                                            "description": "사용자 비밀번호"
                                        }
                                    },
                                    "required": ["username", "password"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "로그인 성공"}
                    }
                }
            },
            "/upload/": {
                "post": {
                    "summary": "파일 업로드 및 분석 후 DB에 저장",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
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
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "파일 업로드 성공"}
                    }
                }
            },
            "/download/{filename}": {
                "get": {
                    "summary": "파일 다운로드",
                    "parameters": [
                        {
                            "in": "path",
                            "name": "filename",
                            "required": True,
                            "schema": {"type": "string", "description": "다운로드할 파일 이름"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "파일 다운로드 성공"}
                    }
                }
            },
            "/delete-file/{filename}": {
                "delete": {
                    "summary": "파일 삭제",
                    "parameters": [
                        {
                            "in": "path",
                            "name": "filename",
                            "required": True,
                            "schema": {"type": "string", "description": "삭제할 파일 이름"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "파일 삭제 성공"}
                    }
                }
            },
            "/chat": {
                "post": {
                    "summary": "RAG 기반 대화 API (GPT-4 모델 사용)",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
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
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "대화 응답 성공"}
                    }
                }
            },
            "/discord-bot": {
                "get": {
                    "summary": "Discord 봇 명령 테스트",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "command",
                            "required": True,
                            "schema": {"type": "string", "description": "봇 명령어"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "Discord 봇 명령 처리 성공"}
                    }
                }
            },
            "/rp-event": {
                "post": {
                    "summary": "RP 이벤트 생성",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string", "description": "생성할 이벤트 이름"}
                                    },
                                    "required": ["event"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "RP 이벤트 생성 성공"}
                    }
                }
            },
            "/game-status": {
                "get": {
                    "summary": "게임 상태 조회",
                    "responses": {
                        "200": {"description": "게임 상태 조회 성공"}
                    }
                }
            },
            "/growth-feedback": {
                "post": {
                    "summary": "사용자 피드백 저장",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user": {"type": "string", "description": "사용자 이름"},
                                        "feedback": {"type": "string", "description": "피드백 내용"}
                                    },
                                    "required": ["user", "feedback"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "피드백 저장 성공"}
                    }
                }
            },
            "/update-personalization": {
                "post": {
                    "summary": "사용자 개인화 설정 업데이트",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user": {"type": "string", "description": "사용자 이름"},
                                        "preferences": {"type": "string", "description": "선호 설정 내용"}
                                    },
                                    "required": ["user", "preferences"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "개인화 설정 업데이트 성공"}
                    }
                }
            },
            "/backup-memory": {
                "post": {
                    "summary": "대화 내용 백업",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user_id": {"type": "string", "description": "사용자 ID"},
                                        "query": {"type": "string", "description": "사용자 입력"},
                                        "response": {"type": "string", "description": "GPT 응답"}
                                    },
                                    "required": ["user_id", "query", "response"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "대화 백업 성공"}
                    }
                }
            },
            "/backup-db": {
                "get": {
                    "summary": "DB 백업",
                    "responses": {
                        "200": {"description": "DB 백업 성공"}
                    }
                }
            }
        }
    }
    return actions_schema
