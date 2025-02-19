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

# ✅ 환경 변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise HTTPException(status_code=500, detail="❌ OPENAI_API_KEY가 설정되지 않았습니다.")

# ✅ FastAPI 설정
app = FastAPI(
    title="DisToPia API",
    description="DTP 세계관 API (DB + AI + RAG + 파일 관리)",
    version="4.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =============================================================================
# ✅ 기본 경로 (404 오류 해결)
# =============================================================================
@app.get("/")
def root():
    return {"message": "DisToPia API is running! 🚀"}

# =============================================================================
# ✅ ChromaDB 벡터 검색 (RAG)
# =============================================================================
def get_chroma_client():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma(collection_name="distopia_collection", persist_directory="chroma_db", embedding_function=embeddings)
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
        base, extension = os.path.splitext(file.filename)
        file.filename = f"{base}_{int(time.time())}{extension}"
        file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ 업로드 완료"}

@app.get("/files/")
def list_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"files": files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="❌ 업로드 폴더가 없습니다.")

@app.get("/download/{filename}/")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="❌ 파일을 찾을 수 없습니다.")

# =============================================================================
# ✅ Pydantic 모델 (Chat 요청)
# =============================================================================
class ChatRequest(BaseModel):
    question: str

# =============================================================================
# ✅ AI 기반 대화 (GPT-4 + LangChain)
# =============================================================================
@app.post("/chat/")
def chat_with_gpt(request: ChatRequest):
    vectordb = get_chroma_client()
    rag_chain = ConversationalRetrievalChain.from_llm(
        ChatOpenAI(model_name="gpt-4", openai_api_key=OPENAI_API_KEY),
        vectordb.as_retriever()
    )
    result = rag_chain.run({"question": request.question})
    return {"response": result}

# =============================================================================
# ✅ DB 검색 API
# =============================================================================
@app.get("/search/")
def search_data(query: str = Query(..., description="검색할 쿼리 문자열")):
    vectordb = get_chroma_client()
    search_results = vectordb.similarity_search(query, k=5)
    return {"results": [doc.page_content for doc in search_results]}

# =============================================================================
# ✅ FastAPI 실행 (Render 배포 최적화)
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Render에서 자동 감지
    uvicorn.run(app, host="0.0.0.0", port=port)
