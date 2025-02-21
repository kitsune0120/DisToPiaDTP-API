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

# 동영상 프레임 추출을 위한 ffmpeg-python (pip install ffmpeg-python)
import ffmpeg

# 문서 파싱 라이브러리
import PyPDF2
import docx

# 이미지 캡션/객체 감지용 라이브러리 (pip install transformers pillow torch)
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from transformers import DetrImageProcessor, DetrForObjectDetection  # 객체 감지 예시
from PIL import Image

# LangChain Community (벡터 검색 / LLM 연동)
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
logger = logging.getLogger()

# -------------------------------
# FastAPI 앱 생성 (커스텀 OpenAPI 사용)
# -------------------------------
app = FastAPI(
    title="DisToPia API (GPT Actions)",
    description="DTP 세계관 API (DB + AI + RAG + 파일 관리 + GPT Actions)",
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

@app.post("/login-for-access-token", operation_id="loginForAccessToken")
def login_for_access_token(user: User):
    if user.username in fake_users_db and fake_users_db[user.username]["password"] == user.password:
        token = create_access_token({"sub": user.username})
        return {"access_token": token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

# -------------------------------
# DB 연결 (단순 예시)
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
# DB 테이블 생성 (dtp_data 및 conversation)
# -------------------------------
@app.get("/create-table", operation_id="createTable")
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
    return {"message": "✅ dtp_data 및 conversation 테이블 생성 완료!"}

# -------------------------------
# ChromaDB (RAG) 세팅
# -------------------------------
def get_chroma_client():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(collection_name="distopia_collection", persist_directory="chroma_db", embedding_function=embeddings)
    return vectordb

# -------------------------------
# 모델 캐싱 (이미지 캡션, 객체 감지)
# -------------------------------
image_caption_model = None
image_processor = None
caption_tokenizer = None

object_detector = None
object_processor = None

def load_image_caption_model():
    global image_caption_model, image_processor, caption_tokenizer
    if image_caption_model is None:
        logger.info("🔍 이미지 캡션 모델 로딩 중...")
        image_caption_model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
        image_processor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
        caption_tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
        logger.info("✅ 이미지 캡션 모델 로딩 완료!")

def load_object_detection_model():
    global object_detector, object_processor
    if object_detector is None:
        logger.info("🔍 객체 감지 모델 로딩 중...")
        object_processor = DetrImageProcessor.from_pretrained("facebook/detr-resnet-50")
        object_detector = DetrForObjectDetection.from_pretrained("facebook/detr-resnet-50")
        logger.info("✅ 객체 감지 모델 로딩 완료!")

# -------------------------------
# 파일명 안전 처리 함수 (경로 조작 공격 방지)
# -------------------------------
def secure_filename(filename: str) -> str:
    filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
    return filename

# -------------------------------
# 미정의 함수 구현: 파일 내용 분석
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
                return text if text else "PDF 파일에서 텍스트를 추출하지 못했습니다."
        elif ext == ".docx":
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text if text else "DOCX 파일에서 텍스트를 추출하지 못했습니다."
        elif ext in [".png", ".jpg", ".jpeg"]:
            load_image_caption_model()  # 모델 로딩
            image = Image.open(file_path)
            pixel_values = image_processor(image, return_tensors="pt").pixel_values
            output_ids = image_caption_model.generate(pixel_values, max_length=16, num_beams=4)
            caption = caption_tokenizer.decode(output_ids[0], skip_special_tokens=True)
            return f"이미지 캡션: {caption}"
        else:
            return f"지원하지 않는 파일 형식({ext})입니다."
    except Exception as e:
        logger.error("파일 분석 중 오류 발생: %s", e)
        return f"파일 분석 중 오류 발생: {e}"

# -------------------------------
# 미정의 함수 구현: 대화 캐시 조회 및 저장 (DB 기반)
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
        logger.error("get_cached_conversation 오류: %s", e)
        return None

def save_conversation(question: str, answer: str):
    conn = get_db_connection()
    if not conn:
        logger.error("DB 연결 실패, 대화 저장 안됨.")
        return
    try:
        cursor = conn.cursor()
        created_at = datetime.utcnow()
        cursor.execute("INSERT INTO conversation (question, answer, created_at) VALUES (%s, %s, %s)", (question, answer, created_at))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("대화 저장 완료.")
    except Exception as e:
        logger.error("save_conversation 오류: %s", e)
        conn.rollback()
        cursor.close()
        conn.close()

# -------------------------------
# 기본 엔드포인트 (루트)
# -------------------------------
@app.get("/", operation_id="rootGet")
def root():
    logger.info("GET / 요청 받음.")
    return {"message": "Hello from DTP (GPT Actions)!"}

# -------------------------------
# DB API
# -------------------------------
@app.post("/add-data", operation_id="addDataPost")
def add_data(name: str, description: str, user: dict = Depends(optional_verify_token)):
    logger.info(f"POST /add-data 요청 받음. 사용자: {user['sub']}")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    cursor.execute("SELECT id, description FROM dtp_data WHERE name = %s", (name,))
    existing = cursor.fetchone()
    if existing:
        new_description = existing[1] + " " + description
        cursor.execute("UPDATE dtp_data SET description = %s WHERE id = %s", (new_description, existing[0]))
        message = f"✅ 기존 데이터 업데이트됨 (name={name})"
    else:
        cursor.execute("INSERT INTO dtp_data (name, description) VALUES (%s, %s)", (name, description))
        message = f"✅ 데이터 추가 성공! (name={name})"
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": message}

@app.get("/get-data", operation_id="getDataGet")
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

@app.put("/update-data/{data_id}", operation_id="updateDataPut")
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

@app.delete("/delete-data/{data_id}", operation_id="deleteDataDelete")
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
# 파일 업로드 및 분석 API
# -------------------------------
@app.post("/upload/", operation_id="uploadFilePost")
async def upload_file(file: UploadFile = File(...)):
    logger.info("POST /upload/ 요청 받음.")
    try:
        # 파일명 안전 처리
        safe_filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        if os.path.exists(file_path):
            base, ext = os.path.splitext(safe_filename)
            file_path = os.path.join(UPLOAD_DIR, f"{base}_{int(time.time())}{ext}")
        
        # 파일 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # ZIP 파일 처리: 내부 압축 해제 후 각각 분석
        if zipfile.is_zipfile(file_path):
            logger.info(f"압축 파일 감지: {file_path}")
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            extract_dir = os.path.join(UPLOAD_DIR, f"{base_name}_extracted_{int(time.time())}")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            conn = get_db_connection()
            if not conn:
                raise HTTPException(status_code=500, detail="DB 연결 실패")
            cursor = conn.cursor()
            # 모든 파일에 대해 분석 수행
            for root, dirs, files in os.walk(extract_dir):
                for fname in files:
                    extracted_path = os.path.join(root, fname)
                    content = analyze_file_content(extracted_path)
                    cursor.execute(
                        "INSERT INTO dtp_data (name, description) VALUES (%s, %s)",
                        (fname, content)
                    )
                    logger.info(f"✅ 파일 {fname} 분석 및 DB 저장 완료")
            conn.commit()
            cursor.close()
            conn.close()
            return {
                "filename": os.path.basename(file_path),
                "message": "ZIP 파일 업로드 및 내부 파일 분석/DB 저장 완료!",
                "extracted_dir": extract_dir
            }
        else:
            # 단일 파일 처리
            content = analyze_file_content(file_path)
            conn = get_db_connection()
            if not conn:
                raise HTTPException(status_code=500, detail="DB 연결 실패")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dtp_data (name, description) VALUES (%s, %s)",
                (os.path.basename(file_path), content)
            )
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error("파일 처리 중 오류 발생: %s", e)
        raise HTTPException(status_code=500, detail=f"파일 업로드/분석에 실패했습니다: {e}")
    
    return {"filename": os.path.basename(file_path), "message": "파일 업로드 및 분석/DB 저장 성공!"}

@app.get("/download/{filename}", operation_id="downloadFileGet")
def download_file(filename: str):
    logger.info(f"GET /download/{filename} 요청 받음.")
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

# -------------------------------
# RAG 기반 대화 API
# -------------------------------
class ChatRequest(BaseModel):
    query: str
    history: List[str] = []

@app.post("/chat", operation_id="chatPost")
def chat(request: ChatRequest):
    logger.info("POST /chat 요청 받음.")
    cached_answer = get_cached_conversation(request.query)
    if cached_answer:
        logger.info("DB 캐시 응답 반환")
        return {"response": cached_answer}
    
    vectordb = get_chroma_client()
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    llm = ChatOpenAI(temperature=0.7, openai_api_key=OPENAI_API_KEY)
    chain = ConversationalRetrievalChain.from_llm(llm, retriever)
    result = chain({"question": request.query, "chat_history": request.history})
    answer = result["answer"]
    
    # 응답을 DB에 저장
    save_conversation(request.query, answer)
    
    return {"response": answer}

# -------------------------------
# 노래 가사 생성 API
# -------------------------------
@app.post("/generate-lyrics/", operation_id="generateLyricsPost")
def generate_lyrics(theme: str):
    logger.info(f"POST /generate-lyrics 요청 받음. Theme: {theme}")
    lyrics = f"이 노래는 '{theme}'에 관한 이야기입니다.\n"
    for _ in range(4):
        lyrics += f"이것은 {theme}에 관한 {random.choice(['사랑', '슬픔', '희망', '기쁨'])}의 가사입니다.\n"
    return {"lyrics": lyrics}

# -------------------------------
# 노래 생성 API (가사 + 구조)
# -------------------------------
@app.post("/generate-song/", operation_id="generateSongPost")
def generate_song(theme: str):
    logger.info(f"POST /generate-song 요청 받음. Theme: {theme}")
    lyrics = generate_lyrics(theme)['lyrics']
    song_structure = {
        "title": f"Song about {theme}",
        "verse1": lyrics.split('\n')[0],
        "chorus": lyrics.split('\n')[1],
        "verse2": lyrics.split('\n')[2],
        "chorus2": lyrics.split('\n')[3],
        "outro": "끝까지 들어주셔서 감사합니다."
    }
    return {"song": song_structure}

# -------------------------------
# Discord 봇 통합 (플레이스홀더)
# -------------------------------
@app.get("/discord-bot", operation_id="discordBotGet")
def discord_bot_command(command: str):
    logger.info(f"GET /discord-bot 요청 받음. Command: {command}")
    return {"message": f"Discord 봇이 '{command}' 명령을 처리했습니다."}

# -------------------------------
# RP 이벤트 생성 (플레이스홀더)
# -------------------------------
@app.post("/rp-event", operation_id="rpEventPost")
def rp_event(event: str):
    logger.info(f"POST /rp-event 요청 받음. Event: {event}")
    return {"message": f"RP 이벤트 '{event}'가 생성되었습니다."}

# -------------------------------
# 게임 상태 조회 (플레이스홀더)
# -------------------------------
@app.get("/game-status", operation_id="gameStatusGet")
def game_status():
    logger.info("GET /game-status 요청 받음.")
    status = {"players": random.randint(1, 100), "score": random.randint(0, 1000), "status": "running"}
    return {"game_status": status}

# -------------------------------
# 커스텀 OpenAPI 함수 (OpenAPI 버전 3.1.0, servers 설정)
# -------------------------------
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="DisToPia API (GPT Actions)",
        version="4.0",
        description="DTP 세계관 API (DB + AI + RAG + 파일 관리 + GPT Actions)",
        routes=app.routes,
    )
    # OpenAPI 버전을 3.1.0으로 강제
    openapi_schema["openapi"] = "3.1.0"
    # Servers 설정: 끝의 슬래시 없이 URL 지정
    openapi_schema["servers"] = [
        {"url": "https://distopiadtp-api.onrender.com", "description": "production server"}
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
