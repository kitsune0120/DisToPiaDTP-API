import os
import psycopg2

# Render 환경 변수에서 DATABASE_URL 가져오기
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    # PostgreSQL 데이터베이스 연결
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # 연결 테스트 (데이터 조회)
    cursor.execute("SELECT NOW();")  # 현재 시간 가져오기
    result = cursor.fetchone()
    
    print("✅ 데이터베이스 연결 성공! 현재 시간:", result[0])

except Exception as e:
    print("❌ 데이터베이스 연결 실패:", e)

finally:
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()
