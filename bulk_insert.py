from fastapi import FastAPI, UploadFile, File, Depends
import pandas as pd
import json
from sqlalchemy.orm import Session
from distopia_api.database import engine, Base, get_db
from distopia_api.models import Character  # 모델에 맞게 변경

app = FastAPI()

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    ✅ 업로드된 CSV, JSON, Excel 파일을 데이터베이스에 저장하는 API
    """
    contents = await file.read()
    filename = file.filename.lower()

    # ✅ 파일 형식 판별
    if filename.endswith(".csv"):
        df = pd.read_csv(file.file)
    elif filename.endswith(".json"):
        df = pd.read_json(file.file)
    elif filename.endswith(".xlsx"):
        df = pd.read_excel(file.file)
    else:
        return {"error": "지원되지 않는 파일 형식입니다. (CSV, JSON, XLSX만 가능)"}

    # ✅ 데이터를 데이터베이스에 삽입
    characters = []
    for _, row in df.iterrows():
        character = Character(
            name=row["name"],
            species=row["species"],
            ability=row["ability"],
            attack_power=row["attack_power"],
            defense_power=row["defense_power"],
            battle_style=row["battle_style"],
            speech_pattern=row["speech_pattern"]
        )
        characters.append(character)

    db.add_all(characters)
    db.commit()

    return {"message": f"{len(characters)}개의 데이터를 성공적으로 추가했습니다!"}
