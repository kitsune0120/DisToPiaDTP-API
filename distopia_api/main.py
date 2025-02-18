# distopia_api/main.py

import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
import openai

# langchain_community와 langchain 혼합 사용
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
# ConversationalRetrievalChain은 langchain에 존재 (community에 없음)
from langchain.chains import ConversationalRetrievalChain

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DTP 세계 확장 API (DB + RAG + 세션)",
    description="이 API는 DisToPia 세계관을 확장하기 위한 모든 기능을 제공합니다.",
    version="3.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 세션 기반 대화(임시). 실제 서버 환경에서는 Redis 등 추천
session_storage = {}

# =============================================================================
# (A) Chroma 벡터 DB 초기화 함수 (RAG용)
# =============================================================================
def get_chroma_client():
    """
    Chroma DB를 초기화한 뒤 반환합니다.
    'chroma_db' 폴더에 벡터 데이터가 영구 저장됩니다.
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
        persist_directory="chroma_db",
        embedding_function=embeddings
    )
    return vectordb

# =============================================================================
# 1. ZIP 파일 업로드/다운로드 기능
# =============================================================================
@app.post("/upload-zip/", summary="ZIP 파일 업로드", description="ZIP 파일을 업로드하여 서버에 저장합니다.")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="ZIP 파일만 업로드할 수 있습니다.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ ZIP 파일 업로드가 완료되었습니다."}

@app.get("/uploaded-files/", summary="업로드된 파일 목록 조회", description="서버에 저장된 업로드 파일을 확인합니다.")
def list_uploaded_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"uploaded_files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 존재하지 않습니다."}

@app.get("/download-file/{filename}/", summary="파일 다운로드", description="업로드된 ZIP 파일을 다운로드합니다.")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/zip")
    return {"error": "해당 파일을 찾을 수 없습니다."}

# =============================================================================
# 2. 저장된 데이터를 JSON, Markdown, HTML 형태로 조회
# =============================================================================
@app.get("/all-data/", summary="전체 데이터 조회 (JSON)", description="캐릭터, 종족, 지역 정보를 모두 JSON 형태로 반환.")
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

@app.get("/formatted-data/", summary="전체 데이터 조회 (Markdown)", description="캐릭터, 종족, 지역 정보를 Markdown으로 보기 좋게 반환합니다.")
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

@app.get("/visualized-data/", summary="전체 데이터 조회 (HTML)", response_class=HTMLResponse)
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

    return html_content

# =============================================================================
# 3. NEW! 데이터 정리
# =============================================================================
@app.post("/confirm-view/", summary="새로운 데이터 정리", description="'new' 상태인 데이터를 모두 정리합니다.")
def confirm_view(db: Session = Depends(get_db)):
    db.query(models.Character).filter(models.Character.new == True).update({"new": False})
    db.query(models.Species).filter(models.Species.new == True).update({"new": False})
    db.query(models.Region).filter(models.Region.new == True).update({"new": False})
    db.commit()
    return {"message": "✅ 새로운 데이터들을 정리했습니다."}

# =============================================================================
# 4. GPT가 기억하는 데이터 저장 (remember)
# =============================================================================
@app.post("/remember/", summary="GPT가 기억하는 데이터 저장", description="카테고리를 지정하고, 이름과 설명을 전달하여 DB에 새 데이터로 추가합니다.")
def remember_data(category: str, name: str, description: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리입니다. (character/species/region)")

    existing_item = db.query(model_map[category]).filter(model_map[category].name == name).first()
    if existing_item:
        existing_item.description = description
        db.commit()
        db.refresh(existing_item)
        return {"message": f"✅ 기존 {category} '{name}'가(이) 업데이트되었습니다."}
    else:
        new_item = model_map[category](name=name, description=description, new=True)
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return {"message": f"✅ 새로운 {category} '{name}'이(가) 저장되었습니다."}

# =============================================================================
# 5. DisToPia 세계관 채팅 (DB 기반)
# =============================================================================
@app.post("/dtp-chat/", summary="DisToPia 세계관 질문", description="질문을 받으면 DB 검색을 통해 관련 정보를 반환합니다.")
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
        response = "❌ 해당 정보가 없습니다. '기억해줘' 기능으로 새로 추가할 수 있습니다."

    return {"message": response}

# =============================================================================
# 6. 데이터 개수 및 최근 업데이트 (data-info)
# =============================================================================
@app.get("/data-info/", summary="데이터 개수 및 최근 업데이트", description="캐릭터, 종족, 지역의 개수와 최근 업데이트 시간 확인.")
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
@app.get("/search-data/", summary="데이터 검색", description="키워드를 사용해 캐릭터, 종족, 지역을 검색합니다.")
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
@app.delete("/delete-data/{category}/{name}/", summary="특정 데이터 삭제", description="캐릭터/종족/지역 중 하나를 지정해 삭제합니다.")
def delete_data(category: str, name: str, db: Session = Depends(get_db)):
    model_map = {
        "character": models.Character,
        "species": models.Species,
        "region": models.Region
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail="잘못된 카테고리입니다.")

    item = db.query(model_map[category]).filter(model_map[category].name == name).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{category} '{name}'을(를) 찾을 수 없습니다.")

    db.delete(item)
    db.commit()
    return {"message": f"✅ {category} '{name}'이(가) 삭제되었습니다."}

# =============================================================================
# 9. RAG: 문서 임베딩 후 GPT에 검색
# =============================================================================
@app.post("/rag/add-data/", summary="RAG용 문서 추가", description="텍스트를 벡터로 임베딩하여 Chroma DB에 저장합니다.")
def add_rag_data(title: str, content: str):
    vectordb = get_chroma_client()
    vectordb.add_texts(texts=[content], metadatas=[{"title": title}])
    vectordb.persist()
    return {"message": f"'{title}' 문서가 Chroma DB에 추가되었습니다."}

@app.post("/rag/chat/", summary="RAG 기반 질의응답", description="Chroma DB에서 문서를 검색 후 GPT가 답변.")
def rag_chat(question: str, history: list = []):
    vectordb = get_chroma_client()
    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0),
        retriever=vectordb.as_retriever(search_kwargs={"k": 3}),
    )
    chat_history = []
    for i in range(0, len(history), 2):
        user_q = history[i]
        ai_a = history[i+1] if i+1 < len(history) else ""
        chat_history.append((u
