import os
import shutil
import time
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends, Request
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
import jwt
import random

# LangChain Community (벡터 검색 / LLM 연동)
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain

# 1) .env 파일 로드 & 환경 변수 체크
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

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# FastAPI 앱 설정
app = FastAPI(
    title="DisToPia API",
    description="DTP 세계관 API (DB + AI + RAG + 파일 관리 + ChatGPT 플러그인 + 노래, 디스코드, RP, 게임 등)",
    version="4.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# OAuth2 (JWT) 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login-for-access-token")

# 사용자 모델 (간단한 예시)
class User(BaseModel):
    username: str
    password: str

# Fake 사용자 DB (실제 서비스에서는 DB 연동 필요)
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "password": "secret"
    }
}

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def ai_plugin_manifest():
    return {
        "schema_version": "v1",
        "name_for_human": "Dystopia API",
        "name_for_model": "dystopia_plugin",
        "description_for_human": "A plugin to interact with the Dystopia system.",
        "description_for_model": "Use this plugin to fetch actions from the Dystopia API.",
        "auth": {
            "type": "none"
        },
        "api": {
            "type": "openapi",
            # 여기에 실제 openapi.json 주소를 적어주세요. 예: http://127.0.0.1:8000/openapi.json
            "url": "http://127.0.0.1:8000/openapi.json",
            "is_user_authenticated": False
        },
        "logo_url": "http://127.0.0.1:8000/logo.png",  # 원하는 로고 이미지 URL
        "contact_email": "support@yourdomain.com",
        "legal_info_url": "http://127.0.0.1:8000/legal"
    }


# JWT 토큰 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

# JWT 검증 (fake 인증 예시)
def fake_verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"sub": username}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# 2) PostgreSQL 연결 함수 (디버그 로그 포함)
def get_db_connection():
    logger.info("🔍 get_db_connection() 호출됨.")
    try:
        logger.info("🔍 DB 연결 시도 중...")
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("✅ 데이터베이스에 성공적으로 연결되었습니다!")
        return conn
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return None

# 3) ChromaDB (RAG) 세팅
def get_chroma_client():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(
        collection_name="distopia_collection",
        persist_directory="chroma_db",
        embedding_function=embeddings
    )
    return vectordb

# 4) 기본 라우트 (테스트용)
@app.get("/")
def root():
    logger.info("GET / 요청 받음.")
    return {"message": "Hello from DTP!"}

# 5) DB 테이블 생성
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

# 6) DB 데이터 추가 (DisToPia 세계관 데이터)
@app.post("/add-data")
def add_data(name: str, description: str, user: dict = Depends(fake_verify_token)):
    logger.info(f"POST /add-data 요청 받음. 사용자: {user['sub']}")
    # 여기서는 DisToPia 세계관 데이터만 다룬다고 가정 (필요에 따라 조건 추가 가능)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    # 중복 데이터 처리: 기존 데이터 있으면 업데이트, 없으면 삽입
    cursor.execute("SELECT id, description FROM dtp_data WHERE name = %s", (name,))
    existing = cursor.fetchone()
    if existing:
        # 기존 description에 새로운 내용을 덧붙임
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

# 7) DB 데이터 조회 (DisToPia 세계관 데이터)
@app.get("/get-data")
def get_data():
    logger.info("GET /get-data 요청 받음.")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    cursor = conn.cursor()
    # 여기서는 모든 데이터를 조회 (필요시 필터링 조건 추가 가능)
    cursor.execute("SELECT * FROM dtp_data;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"data": rows}

# 8) DB 데이터 업데이트 (사용자 요청에 따라)
@app.put("/update-data/{data_id}")
def update_data(data_id: int, name: str, description: str, user: dict = Depends(fake_verify_token)):
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

# 9) DB 데이터 삭제
@app.delete("/delete-data/{data_id}")
def delete_data(data_id: int, user: dict = Depends(fake_verify_token)):
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

# 10) 파일 업로드 API
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    logger.info("POST /upload/ 요청 받음.")
    ext = file.filename.split('.')[-1].lower()
    allowed_extensions = ["zip", "png", "jpg", "jpeg", "mp4", "avi"]
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다.")
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    if os.path.exists(file_path):
        base, extension = os.path.splitext(file.filename)
        new_filename = f"{base}_{int(time.time())}{extension}"
        file_path = os.path.join(UPLOAD_DIR, new_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "message": "파일 업로드 성공!"}

# 11) 파일 다운로드 API
@app.get("/download/{filename}")
def download_file(filename: str):
    logger.info(f"GET /download/{filename} 요청 받음.")
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

# 12) RAG 기반 대화 API
@app.post("/chat")
def chat(query: str, history: list = Query(default=[])):
    logger.info("POST /chat 요청 받음.")
    vectordb = get_chroma_client()
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    llm = ChatOpenAI(temperature=0.7, openai_api_key=OPENAI_API_KEY)
    chain = ConversationalRetrievalChain.from_llm(llm, retriever)
    result = chain({"question": query, "chat_history": history})
    return {"response": result["answer"]}

# 13) 노래 가사 생성 API
@app.post("/generate-lyrics/")
def generate_lyrics(theme: str):
    logger.info(f"POST /generate-lyrics 요청 받음. Theme: {theme}")
    # 예시: 주제에 따라 간단한 노래 가사 생성
    lyrics = f"이 노래는 '{theme}'에 관한 이야기입니다.\n"
    for _ in range(4):
        lyrics += f"이것은 {theme}에 관한 {random.choice(['사랑', '슬픔', '희망', '기쁨'])}의 가사입니다.\n"
    return {"lyrics": lyrics}

# 14) 노래 생성 API (가사와 기본 구조 제공)
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

# 15) Discord 봇 통합 (플레이스홀더 예시)
@app.get("/discord-bot")
def discord_bot_command(command: str):
    logger.info(f"GET /discord-bot 요청 받음. Command: {command}")
    # 실제 Discord 봇 연동 로직은 별도의 Discord API 및 라이브러리를 사용합니다.
    return {"message": f"Discord 봇이 '{command}' 명령을 처리했습니다."}

# 16) RP 이벤트 생성 (플레이스홀더)
@app.post("/rp-event")
def rp_event(event: str):
    logger.info(f"POST /rp-event 요청 받음. Event: {event}")
    # 실제 RP 시스템과 연동하여 이벤트를 생성하는 로직을 추가할 수 있습니다.
    return {"message": f"RP 이벤트 '{event}'가 생성되었습니다."}

# 17) 게임 상태 조회 (플레이스홀더)
@app.get("/game-status")
def game_status():
    logger.info("GET /game-status 요청 받음.")
    # 실제 게임과 연동하여 현재 게임 상태, 플레이어 정보 등을 반환하는 로직
    status = {
        "players": random.randint(1, 100),
        "score": random.randint(0, 1000),
        "status": "running"
    }
    return {"game_status": status}

# 18) 성장형 피드백 (사용자 피드백 수집 및 개인화 업데이트)
feedback_storage = {}  # 간단한 메모리 저장소 (실제 서비스에서는 DB 사용 권장)

@app.post("/growth-feedback")
def growth_feedback(user: str, feedback: str):
    logger.info(f"POST /growth-feedback 요청 받음. 사용자: {user}, 피드백: {feedback}")
    # 기존 피드백이 있으면 합치고, 없으면 새로 저장
    if user in feedback_storage:
        feedback_storage[user] += " " + feedback
    else:
        feedback_storage[user] = feedback
    return {"message": "피드백이 저장되었습니다.", "feedback": feedback_storage[user]}

# 19) 개인화 업데이트 (사용자 맞춤 기능 업데이트)
@app.post("/update-personalization")
def update_personalization(user: str, preferences: str):
    logger.info(f"POST /update-personalization 요청 받음. 사용자: {user}, 선호도: {preferences}")
    # 실제로는 사용자의 선호 정보를 DB나 별도 스토리지에 저장하여 학습에 반영합니다.
    return {"message": f"{user}님의 개인화 설정이 업데이트되었습니다.", "preferences": preferences}

# 백업 폴더 생성 (없으면 자동 생성)
BACKUP_DIR = "D:/backup"
os.makedirs(BACKUP_DIR, exist_ok=True)

# 대화 내용 백업 (자동 저장)
@app.post("/backup-memory")
def backup_memory(user_id: str, query: str, response: str):
    try:
        backup_file = os.path.join(BACKUP_DIR, "memory_logs.txt")
        with open(backup_file, "a", encoding="utf-8") as file:
            file.write(f"{datetime.now()} - User: {user_id}, Query: {query}, Response: {response}\n")
        return {"message": "✅ 대화 내용이 백업되었습니다!"}
    except Exception as e:
        return {"error": f"백업 실패: {e}"}

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return None

# DB 백업 (자동 저장)
@app.get("/backup-db")
def backup_db():
    try:
        backup_file = os.path.join(BACKUP_DIR, "db_backup.sql")
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

# 앱 시작
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
