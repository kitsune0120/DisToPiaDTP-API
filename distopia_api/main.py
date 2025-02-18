from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from distopia_api.database import engine, Base, get_db
import models
import openai

# OpenAI API 키 설정 (GPT 사용 시 필요)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DTP World Expansion API",
    description="DTP 세계관을 사용자의 질문을 기반으로 확장하는 API",
    version="1.1"
)

# ✅ 추가된 기본 라우트
@app.get("/")
def read_root():
    return {"message": "Hello, DisToPia!"}

@app.get("/home")
def home():
    return {"message": "DTP 세계관 API 실행 중!"}

# 📌 **캐릭터 데이터 API**
@app.get("/characters/")
def read_characters(db: Session = Depends(get_db)):
    return db.query(models.Character).all()

@app.post("/characters/")
def create_character(name: str, species: str, ability: str, attack_power: int, defense_power: int, battle_style: str, speech_pattern: str, db: Session = Depends(get_db)):
    new_character = models.Character(
        name=name, species=species, ability=ability, attack_power=attack_power,
        defense_power=defense_power, battle_style=battle_style, speech_pattern=speech_pattern
    )
    db.add(new_character)
    db.commit()
    db.refresh(new_character)
    return new_character

# 📌 **종족 데이터 API**
@app.get("/species/")
def read_species(db: Session = Depends(get_db)):
    return db.query(models.Species).all()

@app.post("/species/")
def create_species(name: str, description: str, abilities: str, db: Session = Depends(get_db)):
    new_species = models.Species(name=name, description=description, abilities=abilities)
    db.add(new_species)
    db.commit()
    db.refresh(new_species)
    return new_species

# 📌 **조직 및 세력 데이터 API**
@app.get("/factions/")
def read_factions(db: Session = Depends(get_db)):
    return db.query(models.Faction).all()

@app.post("/factions/")
def create_faction(name: str, description: str, leader: str, db: Session = Depends(get_db)):
    new_faction = models.Faction(name=name, description=description, leader=leader)
    db.add(new_faction)
    db.commit()
    db.refresh(new_faction)
    return new_faction

# 📌 **지역 데이터 API**
@app.get("/locations/")
def read_locations(db: Session = Depends(get_db)):
    return db.query(models.Location).all()

@app.post("/locations/")
def create_location(name: str, description: str, history: str, db: Session = Depends(get_db)):
    new_location = models.Location(name=name, description=description, history=history)
    db.add(new_location)
    db.commit()
    db.refresh(new_location)
    return new_location

# 📌 **기술 데이터 API**
@app.get("/technologies/")
def read_technologies(db: Session = Depends(get_db)):
    return db.query(models.Technology).all()

@app.post("/technologies/")
def create_technology(name: str, category: str, description: str, db: Session = Depends(get_db)):
    new_technology = models.Technology(name=name, category=category, description=description)
    db.add(new_technology)
    db.commit()
    db.refresh(new_technology)
    return new_technology

# 📌 **역사적 사건 데이터 API**
@app.get("/historical_events/")
def read_events(db: Session = Depends(get_db)):
    return db.query(models.HistoricalEvent).all()

@app.post("/historical_events/")
def create_event(name: str, description: str, year: int, related_faction: int, db: Session = Depends(get_db)):
    new_event = models.HistoricalEvent(name=name, description=description, year=year, related_faction=related_faction)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

# 📌 **GPT 연동용 검색 API**
@app.get("/search/")
def search_data(query: str, db: Session = Depends(get_db)):
    characters = db.query(models.Character).filter(models.Character.name.contains(query)).all()
    species = db.query(models.Species).filter(models.Species.name.contains(query)).all()
    factions = db.query(models.Faction).filter(models.Faction.name.contains(query)).all()
    technologies = db.query(models.Technology).filter(models.Technology.name.contains(query)).all()
    events = db.query(models.HistoricalEvent).filter(models.HistoricalEvent.name.contains(query)).all()

    return {
        "characters": characters,
        "species": species,
        "factions": factions,
        "technologies": technologies,
        "historical_events": events
    }

# 📌 **질문 기반 확장 API (사용자가 답변해야 추가됨)**
@app.post("/expand/species/")
def expand_species_request():
    return {
        "message": "새로운 종족을 추가하려면 아래 정보를 입력해주세요.",
        "questions": [
            "종족의 이름은 무엇인가요?",
            "이 종족의 고유 능력은 무엇인가요?",
            "이 종족은 어디에서 살고 있나요?"
        ]
    }

@app.post("/expand/species/submit/")
def submit_species(name: str, abilities: str, habitat: str, db: Session = Depends(get_db)):
    new_species = models.Species(name=name, description=f"{name}은(는) {habitat}에서 살아가는 종족입니다.", abilities=abilities)
    db.add(new_species)
    db.commit()
    db.refresh(new_species)
    return {"message": f"새로운 종족 '{name}'이(가) 추가되었습니다!"}

# 📌 **GPT를 활용한 질문 자동 생성 API**
@app.post("/expand/species/gpt/")
def expand_species_with_gpt():
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 DTP 세계관 확장을 위한 질문을 생성하는 AI입니다."},
            {"role": "user", "content": "새로운 종족을 추가하려면 어떤 질문을 해야 할까요?"}
        ]
    )
    return response
