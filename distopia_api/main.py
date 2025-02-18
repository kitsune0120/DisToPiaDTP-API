import sys
import os
import shutil
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
import openai

# ✅ 프로젝트 경로
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ✅ 내부 모듈 임포트
from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

# ✅ OpenAI API 키 설정
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# ✅ 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# ✅ FastAPI 애플리케이션
app = FastAPI(
    title="DTP 세계 확장 API",
    description="이 API는 DTP 세계관을 확장하는 기능을 제공합니다.",
    version="2.0"
)

# ✅ 업로드 폴더 설정
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =============================================================================
# 1) ZIP 파일 업로드 및 다운로드
# =============================================================================
@app.post("/upload-zip/", summary="ZIP 파일 업로드", description="ZIP 파일을 업로드하여 서버에 저장")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="ZIP 파일만 업로드할 수 있습니다.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ ZIP 파일 업로드 완료"}

@app.get("/uploaded-files/", summary="업로드된 파일 목록 조회")
def list_uploaded_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"uploaded_files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 존재하지 않습니다."}

@app.get("/download-file/{filename}/", summary="ZIP 파일 다운로드")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/zip")
    return {"error": "파일을 찾을 수 없습니다."}

# =============================================================================
# 2) 모든 데이터 조회 (JSON / Markdown / HTML)
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
# 3) NEW! 데이터 정리 (confirm-view)
# =============================================================================
@app.post("/confirm-view/", summary="새로운 데이터 정리", description="새로운 데이터를 확인하면 'new' 상태를 False로 변경합니다.")
def confirm_view(db: Session = Depends(get_db)):
    db.query(models.Character).filter(models.Character.new == True).update({"new": False})
    db.query(models.Species).filter(models.Species.new == True).update({"new": False})
    db.query(models.Region).filter(models.Region.new == True).update({"new": False})
    db.commit()
    return {"message": "✅ 새로운 데이터가 정리되었습니다."}

# =============================================================================
# 4) GPT가 기억하는 데이터 저장 (remember)
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
# 5) DisToPia 세계관 채팅 (DB 기반)
# =============================================================================
@app.post("/dtp-chat/", summary="DisToPia 세계관 질문", description="질문에 대해 DB에서 검색 후 답변")
def dtp_chat(question: str, db: Session = Depends(get_db)):
    response = ""

    # 캐릭터 검색
    characters = db.query(models.Character).filter(models.Character.name.contains(question)).all()
    if characters:
        response += "📌 캐릭터 정보:\n"
        for char in characters:
            response += f"- {char.name} ({char.species})\n"

    # 종족 검색
    species = db.query(models.Species).filter(models.Species.name.contains(question)).all()
    if species:
        response += "📌 종족 정보:\n"
        for spec in species:
            response += f"- {spec.name}\n  설명: {spec.description}\n"

    # 지역 검색
    regions = db.query(models.Region).filter(models.Region.name.contains(question)).all()
    if regions:
        response += "📌 지역 정보:\n"
        for reg in regions:
            response += f"- {reg.name}\n  설명: {reg.description}\n"

    if not response:
        response = "❌ 해당 정보가 없습니다. '기억해줘' 기능으로 추가할 수 있습니다."

    return {"message": response}

# =============================================================================
# 6) 데이터 개수 및 최근 업데이트 (data-info)
# =============================================================================
@app.get("/data-info/", summary="데이터 개수 및 최근 업데이트 확인")
def get_data_info(db: Session = Depends(get_db)):
    char_count = db.query(models.Character).count()
    species_count = db.query(models.Species).count()
    region_count = db.query(models.Region).count()

    # 최근 업데이트 시간 (Character.updated_at 기반 예시)
    latest_update = db.query(models.Character.updated_at).order_by(models.Character.updated_at.desc()).first()
    latest_update_time = latest_update[0] if latest_update else "데이터 없음"

    return {
        "캐릭터 개수": char_count,
        "종족 개수": species_count,
        "지역 개수": region_count,
        "최근 업데이트 시간": latest_update_time
    }

# =============================================================================
# 7) 검색 기능 (search-data)
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
# 8) 특정 데이터 삭제 (delete-data)
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
# 9) Render 자동 포트 설정
# =============================================================================
import uvicorn

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
