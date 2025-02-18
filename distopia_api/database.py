# distopia_api/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite DB 예시 (파일형). Render에서 PostgreSQL 등을 사용하려면 이 부분 변경
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 특수 옵션
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """DB 세션을 제공하는 종속성 함수"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
