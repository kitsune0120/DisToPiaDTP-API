import sys
import os
import shutil
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
import openai

# ✅ 프로젝트 루트 경로 추가 (모듈 인식 문제 해결)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ✅ 내부 모듈 임포트
from distopia_api.database import engine, Base, get_db
from distopia_api.models import models

# ✅ OpenAI API 키 설정 (GPT 사용 시 필요)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# ✅ 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# ✅ FastAPI 애플리케이션 생성
app = FastAPI(
    title="DTP 세계 확장 API",
    description="이 API는 DTP 세계관을 확장하는 기능을 제공합니다.",
    version="1.3"
)

# ✅ **📌 ZIP 파일 업로드 기능**
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # 업로드 디렉토리 자동 생성

@app.post("/upload-zip/", summary="ZIP 파일 업로드", description="ZIP 파일을 업로드하여 서버에 저장하는 기능입니다.")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="ZIP 파일만 업로드할 수 있습니다.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "✅ ZIP 파일이 성공적으로 업로드 및 저장되었습니다!"}

# ✅ **📌 업로드된 파일 목록 조회 API**
@app.get("/uploaded-files/", summary="업로드된 파일 목록 조회", description="서버에 저장된 파일 목록을 반환합니다.")
def list_uploaded_files():
    try:
        files = os.listdir(UPLOAD_DIR)
        return {"uploaded_files": files}
    except FileNotFoundError:
        return {"error": "업로드 폴더가 존재하지 않습니다."}

# ✅ **📌 업로드된 파일 다운로드 API**
@app.get("/download-file/{filename}/", summary="파일 다운로드", description="업로드된 ZIP 파일을 다운로드합니다.")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/zip")
    return {"error": "파일을 찾을 수 없습니다."}

# ✅ **📌 저장된 모든 데이터 JSON으로 반환 (`GET /all-data/`)**
@app.get("/all-data/", summary="모든 저장된 데이터 조회", description="서버에 저장된 모든 데이터를 반환합니다.")
def get_all_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    data = {
        "characters": [{"name": char.name, "species": char.species, "ability": char.ability, "attack_power": char.attack_power, "defense_power": char.defense_power} for char in characters],
        "species": [{"name": spec.name, "description": spec.description, "abilities": spec.abilities} for spec in species],
        "regions": [{"name": reg.name, "description": reg.description, "climate": reg.climate} for reg in regions]
    }
    return data

# ✅ **📌 Markdown 형식으로 저장된 데이터 반환 (`GET /formatted-data/`)**
@app.get("/formatted-data/", summary="서버 저장 데이터 보기", description="저장된 데이터를 Markdown 형식으로 변환하여 보기 쉽게 표시합니다.")
def get_formatted_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    markdown_data = "# 📜 저장된 데이터\n\n"

    markdown_data += "## 🏅 캐릭터 목록\n"
    for char in characters:
        markdown_data += f"- **{char.name}** ({char.species})\n  - 🛠 능력: {char.ability}\n  - ⚔️ 공격력: {char.attack_power}, 🛡 방어력: {char.defense_power}\n\n"

    markdown_data += "## 🦊 종족 목록\n"
    for spec in species:
        markdown_data += f"- **{spec.name}**\n  - 설명: {spec.description}\n  - 🧬 능력: {spec.abilities}\n\n"

    markdown_data += "## 🌍 지역 목록\n"
    for reg in regions:
        markdown_data += f"- **{reg.name}**\n  - 🏞️ 설명: {reg.description}\n  - 🌦️ 기후: {reg.climate}\n\n"

    return {"formatted_data": markdown_data}

# ✅ **📌 HTML 형식으로 저장된 데이터 보기 (`GET /visualized-data/`)**
@app.get("/visualized-data/", summary="저장된 데이터를 HTML로 보기", response_class=HTMLResponse)
def get_visualized_data(db: Session = Depends(get_db)):
    characters = db.query(models.Character).all()
    species = db.query(models.Species).all()
    regions = db.query(models.Region).all()

    html_content = """
    <html>
    <head>
        <title>저장된 데이터 보기</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; padding: 20px; }
            h1, h2 { color: #4A90E2; }
            .section { margin-bottom: 20px; }
            img { max-width: 300px; display: block; margin-top: 10px; }
            video { max-width: 400px; display: block; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>📜 저장된 데이터</h1>
    """

    for char in characters:
        html_content += f"<p><strong>{char.name}</strong> ({char.species})</p>"
        html_content += f"<p>🛠 능력: {char.ability}</p>"
        html_content += f"<p>⚔️ 공격력: {char.attack_power}, 🛡 방어력: {char.defense_power}</p>"

    for spec in species:
        html_content += f"<p><strong>{spec.name}</strong></p>"
        html_content += f"<p>설명: {spec.description}</p>"
        html_content += f"<p>🧬 능력: {spec.abilities}</p>"

    for reg in regions:
        html_content += f"<p><strong>{reg.name}</strong></p>"
        html_content += f"<p>🏞️ 설명: {reg.description}</p>"
        html_content += f"<p>🌦️ 기후: {reg.climate}</p>"

    html_content += "</body></html>"
    return HTMLResponse(content=html_content)

# ✅ **🚀 Render 자동 포트 설정**
import uvicorn

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
