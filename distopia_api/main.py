import os
import shutil
import time
import logging
import random
import io
import zipfile
import re  # 파일명 sanitize를 위해 추가
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
# 1) .env 파일 로드 & 환경 변수 설정
# -------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")  # JWT 발급용 비밀키

# 운영 시 민감 정보 출력은 주석 처리하거나 제거할 것
# print(f"📌 현재 설정된 OPENAI_API_KEY: {OPENAI_API_KEY}")
# print(f"📌 현재 설정된 DATABASE_URL: {DATABASE_URL}")

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

@app.post("/login-for-access-token")
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
        # DETR 모델 예시 (실제 사용 시 하드웨어에 맞춰 최적화 필요)
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
# 파일 형식별 분석 함수들
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
            # 수정된 부분: id2label 매핑을 통해 정수 인덱스를 레이블로 변환
            pred_logits = outputs.logits  # (batch_size, num_queries, num_classes)
            pred_classes = pred_logits.argmax(dim=-1)  # (batch_size, num_queries)
            top_indices = pred_classes[0][:3].tolist()  # 첫 번째 배치의 상위 3개 결과
            labels = [object_detector.config.id2label.get(idx, str(idx)) for idx in top_indices]
            detected = "객체: " + ", ".join(labels)
            result += f"[객체 감지] {detected}"
    except Exception as e:
        result += f"[오류] 이미지 분석 실패: {e}"
    return result

def analyze_video(file_path: str) -> str:
    # 동영상에서 일정 간격으로 프레임을 추출 후 이미지 분석 수행
    captions = []
    try:
        # 프레임 추출: 예시로 10초마다 한 프레임 추출 (실제는 동영상 길이에 따라 조정)
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
            # 이미지 분석: 캡션 생성 (객체 감지도 가능)
            cap = analyze_image(out_file)
            captions.append(cap)
            os.remove(out_file)  # 임시 프레임 파일 삭제
        # 종합 요약 (여기서는 단순 연결; 실제로는 LLM을 활용한 요약 가능)
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
# 기본 라우트 (테스트용)
# -------------------------------
@app.get("/")
def root():
    logger.info("GET / 요청 받음.")
    return {"message": "Hello from DTP (GPT Actions)!"}

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
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "✅ dtp_data 테이블 생성 완료!"}

@app.post("/add-data")
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
# 파일 업로드 및 분석 API (최고의 확장 기능)
# -------------------------------
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    logger.info("POST /upload/ 요청 받음.")
    try:
        # 파일명 안전 처리: 클라이언트가 전달한 파일명을 sanitize 함
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
            # 단일 파일 처리: 모든 확장자 지원 (txt, pdf, docx, 이미지, 동영상 등)
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

@app.get("/download/{filename}")
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

@app.post("/chat")
def chat(request: ChatRequest):
    logger.info("POST /chat 요청 받음.")
    vectordb = get_chroma_client()
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    llm = ChatOpenAI(temperature=0.7, openai_api_key=OPENAI_API_KEY)
    chain = ConversationalRetrievalChain.from_llm(llm, retriever)
    result = chain({"question": request.query, "chat_history": request.history})
    return {"response": result["answer"]}

# -------------------------------
# 노래 가사 생성 API
# -------------------------------
@app.post("/generate-lyrics/")
def generate_lyrics(theme: str):
    logger.info(f"POST /generate-lyrics 요청 받음. Theme: {theme}")
    lyrics = f"이 노래는 '{theme}'에 관한 이야기입니다.\n"
    for _ in range(4):
        lyrics += f"이것은 {theme}에 관한 {random.choice(['사랑', '슬픔', '희망', '기쁨'])}의 가사입니다.\n"
    return {"lyrics": lyrics}

# -------------------------------
# 노래 생성 API (가사+구조)
# -------------------------------
@app.post("/generate-song/")
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
    status = {"players": random.randint(1, 100), "score": random.randint(0, 1000), "status": "running"}
    return {"game_status": status}

# (기타 성장형 피드백, 개인화 업데이트, 백업 API 등은 기존 코드 유지)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
