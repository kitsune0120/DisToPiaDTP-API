import pandas as pd
from sqlalchemy.orm import Session
from distopia_api.database import engine, get_db
import distopia_api.models as models

# 데이터베이스 세션 생성
db = next(get_db())

# CSV 파일 로드
df = pd.read_csv("extracted_data/characters.csv")  # CSV 파일 이름 변경

# 데이터 삽입
for _, row in df.iterrows():
    new_character = models.Character(
        name=row["name"],
        species=row["species"],
        ability=row["ability"],
        attack_power=row["attack_power"],
        defense_power=row["defense_power"],
        battle_style=row["battle_style"],
        speech_pattern=row["speech_pattern"]
    )
    db.add(new_character)

db.commit()
print("✅ 데이터 업로드 완료!")
