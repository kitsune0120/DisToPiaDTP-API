import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
import openai

# langchain_community 대신에:
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# ❗️ ConversationalRetrievalChain은 langchain_community에 아직 없으므로:
from langchain.chains import ConversationalRetrievalChain

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DTP 세계 확장 API (RAG + 세션 대화 포함)",
    description="이 API는 DTP 세계관을 확장하기 위한 모든 기능을 제공합니다. (ZIP 업로드, DB, RAG, 세션 대화 등)",
    version="3.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 세션 기반 대화 (임시 저장). 실제 서버에는 Redis 등 사용 권장
session_storage = {}

# =============================================================================
# A. Chroma 벡터 DB 초기화 함수 (RAG용)
# =============================================================================
def get_chroma_client():
    """
    Chroma DB를 초기화하고 반환합니다.
    'chroma_db' 폴더에 벡터 데이터를 영구 저장합니다.
    """
    api_key = os.environ.get("OPENAI_API_KEY", OPENAI_API_KEY)
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
    
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        openai_api_key=api_key
    )
    vectordb = Chroma(
        collection_name="distopia_collection",
        persist_directory="chroma_db",  # DB 데이터 저장 폴더
        embedding_function=embeddings
    )
    return vectordb

# =============================================================================
# 1. ZIP 파일 업로드/다운로드 기능
# =============================================================================
@app.post("/upload-zip/", summary="ZIP 파일 업로드")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="ZIP 파일만 업로드할 수 있습니다.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ ZIP 파일이 성공적으로 업로드되었습니다!"}

@app.get("/uploaded-files/", summary="업로드된 파일 목록 조회")
def list_uploaded_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"uploaded_files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 존재하지 않습니다."}

@app.get("/download-file/{filename}/", summary="파일 다운로드")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/zip")
    return {"error": "파일을 찾을 수 없습니다."}

# =============================================================================
# 2. 저장된 데이터를 JSON, Markdown, HTML로 보기
# =============================================================================
@app.get("/all-data/", summary="모든 데이터 조회 (JSON)")
def get_all_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    data = {
        "캐릭터 목록": [
            {
                "이름": f"🆕 {char.name}" if char.new else char.name,
                "종족": char.species
            }
            for char in characters
        ],
        "종족 목록": [
            {
                "이름": f"🆕 {spec.name}" if spec.new else spec.name,
                "설명": spec.description
            }
            for spec in species
        ],
        "지역 목록": [
            {
                "이름": f"🆕 {reg.name}" if reg.new else reg.name,
                "설명": reg.description
            }
            for reg in regions
        ]
    }
    return data

@app.get("/formatted-data/", summary="모든 데이터 조회 (Markdown)")
def get_formatted_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    markdown_data = "# 📜 저장된 데이터\n\n"
    markdown_data += "## 🏅 캐릭터 목록\n"
    for char in characters:
        prefix = "🆕 " if char.new else ""
        markdown_data += f"- **{prefix}{char.name}** ({char.species})\n"
    markdown_data += "\n## 🦊 종족 목록\n"
    for spec in species:
        prefix = "🆕 " if spec.new else ""
        markdown_data += f"- **{prefix}{spec.name}**\n  - 설명: {spec.description}\n\n"
    markdown_data += "## 🌍 지역 목록\n"
    for reg in regions:
        prefix = "🆕 " if reg.new else ""
        markdown_data += f"- **{prefix}{reg.name}**\n  - 설명: {reg.description}\n\n"

    return {"formatted_data": markdown_data}

@app.get("/visualized-data/", summary="모든 데이터 조회 (HTML)", response_class=HTMLResponse)
def get_visualized_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    html_content = """
    <html>
    <head>
        <title>저장된 데이터</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2 { color: #4A90E2; }
            .new-tag { color: red; font-weight: bold; }
        </style>
    </head>
    <body>
    <h1>📜 저장된 데이터</h1>
    <h2>🏅 캐릭터 목록</h2>
    """
    for char in characters:
        prefix = "<span class='new-tag'>🆕</span> " if char.new else ""
        html_content += f"<p>{prefix}<strong>{char.name}</strong> ({char.species})</p>"

    html_content += "<h2>🦊 종족 목록</h2>"
    for spec in species:
        prefix = "<span class='new-tag'>🆕</span> " if spec.new else ""
        html_content += f"<p>{prefix}<strong>{spec.name}</strong> - 설명: {spec.description}</p>"

    html_content += "<h2>🌍 지역 목록</h2>"
    for reg in regions:
        prefix = "<span class='new-tag'>🆕</span> " if reg.new else ""
        html_content += f"<p>{prefix}<strong>{reg.name}</strong> - 설명: {reg.description}</p>"
    html_content += "</body></html>"
    return HTMLResponse(content=html_content)

# =============================================================================
# 3. NEW! 데이터 정리 (confirm-view)
# =============================================================================
@app.post("/confirm-view/", summary="새로운 데이터 정리", description="새로운 데이터를 확인하면 'new' 상태를 False로 변경합니다.")
def confirm_view(db: Session = Depends(get_db)):
    db.query(models.Character).filter(models.Character.new == True).update({"new": False})
    db.query(models.Species).filter(models.Species.new == True).update({"new": False})
    db.query(models.Region).filter(models.Region.new == True).update({"new": False})
    db.commit()
    return {"message": "✅ 새로운 데이터가 정리되었습니다."}

# =============================================================================
# 4. GPT가 기억하는 데이터 저장 (remember)
# =============================================================================
@app.post("/remember/", summary="GPT가 기억하는 데이터 저장")
def remember_data(category: str, name: str, description: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리. 'character', 'species', 'region' 중 선택하세요.")

    existing_item = db.query(model_map[category]).filter(model_map[category].name == name).first()
    if existing_item:
        existing_item.description = description
        db.commit()
        db.refresh(existing_item)
        return {"message": f"✅ 기존 {category} '{name}' 정보가 업데이트되었습니다."}
    else:
        new_item = model_map[category](name=name, description=description, new=True)
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return {"message": f"✅ 새로운 {category} '{name}'이(가) 저장되었습니다."}

# =============================================================================
# 5. DisToPia 세계관 채팅 (DB 기반)
# =============================================================================
@app.post("/dtp-chat/", summary="DisToPia 세계관 질문", description="질문에 대해 DB에서 검색 후 답변")
def dtp_chat(question: str, db: Session = Depends(get_db)):
    response = ""

    characters = db.query(models.Character).filter(models.Character.name.contains(question)).all()
    if characters:
        response += "📌 캐릭터 정보:\n"
        for char in characters:
            response += f"- {char.name} ({char.species})\n"

    species = db.query(models.Species).filter(models.Species.name.contains(question)).all()
    if species:
        response += "📌 종족 정보:\n"
        for spec in species:
            response += f"- {spec.name}\n  설명: {spec.description}\n"

    regions = db.query(models.Region).filter(models.Region.name.contains(question)).all()
    if regions:
        response += "📌 지역 정보:\n"
        for reg in regions:
            response += f"- {reg.name}\n  설명: {reg.description}\n"

    if not response:
        response = "❌ 해당 정보가 없습니다. '기억해줘' 기능으로 추가할 수 있습니다."

    return {"message": response}

# =============================================================================
# 6. 데이터 개수 및 최근 업데이트 (data-info)
# =============================================================================
@app.get("/data-info/", summary="데이터 개수 및 최근 업데이트 확인")
def get_data_info(db: Session = Depends(get_db)):
    char_count = db.query(models.Character).count()
    species_count = db.query(models.Species).count()
    region_count = db.query(models.Region).count()

    latest_update = db.query(models.Character.updated_at).order_by(models.Character.updated_at.desc()).first()
    latest_update_time = latest_update[0] if latest_update else "데이터 없음"

    return {
        "캐릭터 개수": char_count,
        "종족 개수": species_count,
        "지역 개수": region_count,
        "최근 업데이트 시간": latest_update_time
    }

# =============================================================================
# 7. 검색 기능 (search-data)
# =============================================================================
@app.get("/search-data/", summary="데이터 검색", description="키워드로 캐릭터, 종족, 지역 검색")
def search_data(query: str, db: Session = Depends(get_db)):
    characters = db.query(models.Character).filter(models.Character.name.contains(query)).all()
    species = db.query(models.Species).filter(models.Species.name.contains(query)).all()
    regions = db.query(models.Region).filter(models.Region.name.contains(query)).all()

    return {
        "검색된 캐릭터": [f"{char.name} ({char.species})" for char in characters],
        "검색된 종족": [f"{spec.name} - {spec.description}" for spec in species],
        "검색된 지역": [f"{reg.name} - {reg.description}" for reg in regions]
    }

# =============================================================================
# 8. 특정 데이터 삭제 (delete-data)
# =============================================================================
@app.delete("/delete-data/{category}/{name}/", summary="특정 데이터 삭제", description="캐릭터/종족/지역 데이터 중 특정 항목 삭제")
def delete_data(category: str, name: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리. 'character', 'species', 'region' 중 선택")

    item = db.query(model_map[category]).filter(model_map[category].name == name).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{category} '{name}'을(를) 찾을 수 없습니다.")

    db.delete(item)
    db.commit()
    return {"message": f"✅ {category} '{name}'이(가) 삭제되었습니다."}

# =============================================================================
# 9. RAG: 문서 임베딩 후 GPT에 검색
# =============================================================================
@app.post("/rag/add-data/", summary="RAG용 문서 추가", description="텍스트를 임베딩 후 Chroma DB에 저장")
def add_rag_data(title: str, content: str):
    vectordb = get_chroma_client()
    vectordb.add_texts(texts=[content], metadatas=[{"title": title}])
    vectordb.persist()
    return {"message": f"'{title}' 문서가 RAG DB에 추가되었습니다!"}

@app.post("/rag/chat/", summary="RAG 기반 질의응답", description="Chroma DB에서 문서를 검색 후 GPT가 답변")
def rag_chat(question: str, history: list = []):
    vectordb = get_chroma_client()

    # ❗️ ConversationalRetrievalChain은 langchain.chains에서 가져옴
    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0),
        retriever=vectordb.as_retriever(search_kwargs={"k": 3}),
    )

    # history는 [userQ, aiA, userQ, aiA, ...]
    chat_history = []
    for i in range(0, len(history), 2):
        user_q = history[i]
        ai_a = history[i+1] if i+1 < len(history) else ""
        chat_history.append((user_q, ai_a))

    result = chain({"question": question, "chat_history": chat_history})
    return {"answer": result["answer"]}

# =============================================================================
# 10. RAG + 세션 기반 대화
# =============================================================================
@app.post("/rag/session-chat/", summary="세션 기반 RAG 대화")
def rag_session_chat(session_id: str, question: str):
    if session_id not in session_storage:
        session_storage[session_id] = []

    history = session_storage[session_id]
    vectordb = get_chroma_client()

    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0),
        retriever=vectordb.as_retriever(search_kwargs={"k": 3}),
    )

    # 기존 대화 = [(userQ, aiA), (userQ, aiA), ...]
    chat_history = []
    for i in range(0, len(history), 2):
        user_q = history[i]
        ai_a = history[i+1] if i+1 < len(history) else ""
        chat_history.append((user_q, ai_a))

    result = chain({"question": question, "chat_history": chat_history})
    answer = result["answer"]

    session_storage[session_id].append(question)
    session_storage[session_id].append(answer)

    return {"answer": answer, "session_history": session_storage[session_id]}

# =============================================================================
# 11. Render 자동 포트 설정
# =============================================================================
import uvicorn

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
