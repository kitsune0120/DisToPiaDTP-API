import streamlit as st
import requests

# FastAPI 백엔드의 기본 URL (로컬 테스트 시)
API_URL = "http://127.0.0.1:8000"

def join_url(*parts):
    return "/".join(part.strip("/") for part in parts if part)

st.set_page_config(page_title="DisToPia 통합 클라이언트 (Local)", layout="wide")
st.title("DisToPia 통합 클라이언트 (Local)")

# 세션 상태에 토큰 저장 (로그인 용도)
if "token" not in st.session_state:
    st.session_state["token"] = None

def get_auth_headers():
    if st.session_state["token"]:
        return {"Authorization": f"Bearer {st.session_state['token']}"}
    return {}

# ─────────────────────────────────────────────
# 탭 구성: 로그인, 파일 관리, 대화, DB 관리, 기타 액션
# ─────────────────────────────────────────────
tabs = st.tabs(["로그인", "파일 관리", "대화", "DB 관리", "기타 액션"])

# --- 탭 1: 로그인 ---
with tabs[0]:
    st.header("로그인 (JWT 토큰 발급)")
    username = st.text_input("아이디", key="login_username")
    password = st.text_input("비밀번호", type="password", key="login_password")
    if st.button("로그인"):
        try:
            url = join_url(API_URL, "login-for-access-token")
            response = requests.post(url, json={"username": username, "password": password})
            if response.status_code == 200:
                token = response.json().get("access_token")
                if token:
                    st.session_state["token"] = token
                    st.success("로그인 성공!")
                else:
                    st.error("로그인 실패: 토큰 없음")
            else:
                st.error(f"로그인 실패: {response.json().get('detail', '오류 발생')}")
        except Exception as e:
            st.error(f"로그인 중 예외 발생: {e}")
    if st.session_state["token"]:
        st.info(f"현재 토큰: {st.session_state['token']}")

# --- 탭 2: 파일 관리 ---
with tabs[1]:
    st.header("파일 관리")
    
    st.subheader("파일 업로드")
    uploaded_file = st.file_uploader(
        "파일 선택 (ZIP, 이미지, 텍스트 등)",
        type=["zip", "png", "jpg", "jpeg", "pdf", "docx", "txt"],
        key="file_upload"
    )
    if uploaded_file and st.button("파일 업로드"):
        try:
            url = join_url(API_URL, "upload")
            files = {"file": uploaded_file}
            response = requests.post(url, files=files, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(f"업로드 성공: {response.json().get('filename', '')}")
            else:
                st.error(response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"파일 업로드 중 예외 발생: {e}")
    
    st.subheader("파일 다운로드")
    download_filename = st.text_input("다운로드할 파일명", key="download_filename")
    if download_filename and st.button("파일 다운로드"):
        try:
            url = join_url(API_URL, "download", download_filename)
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.download_button("다운로드", data=response.content, file_name=download_filename)
            else:
                st.error(response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"파일 다운로드 중 예외 발생: {e}")
    
    st.subheader("파일 삭제")
    del_filename = st.text_input("삭제할 파일명", key="del_filename")
    if del_filename and st.button("파일 삭제"):
        try:
            url = join_url(API_URL, "delete-file", del_filename)
            response = requests.delete(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "파일 삭제 성공"))
            else:
                st.error(response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"파일 삭제 중 예외 발생: {e}")

# --- 탭 3: 대화 ---
with tabs[2]:
    st.header("대화")
    chat_query = st.text_input("질문 입력", key="chat_query")
    chat_history = st.text_area("대화 기록 (줄바꿈 구분, 선택)", key="chat_history")
    if st.button("질문하기"):
        if chat_query:
            try:
                url = join_url(API_URL, "chat")
                history_list = chat_history.splitlines() if chat_history else []
                payload = {"query": chat_query, "history": history_list}
                response = requests.post(url, json=payload, headers=get_auth_headers())
                if response.status_code == 200:
                    st.write("응답:", response.json().get("response", "응답 없음"))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"대화 중 예외 발생: {e}")
        else:
            st.warning("질문을 입력하세요.")

# --- 탭 4: DB 관리 ---
with tabs[3]:
    st.header("DB 관리")
    st.subheader("테이블 생성")
    st.write("FastAPI 서버의 `/create-table` 엔드포인트를 호출하여 DB 테이블을 생성합니다.")
    if st.button("테이블 생성 요청"):
        try:
            url = join_url(API_URL, "create-table")
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "테이블 생성 완료"))
            else:
                st.error(response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"테이블 생성 중 예외 발생: {e}")
    
    st.subheader("데이터 추가")
    data_name = st.text_input("데이터 이름", key="data_name")
    data_description = st.text_area("데이터 설명", key="data_description")
    if st.button("데이터 추가 요청"):
        try:
            url = join_url(API_URL, "add-data")
            payload = {"name": data_name, "description": data_description}
            response = requests.post(url, json=payload, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "데이터 추가 성공"))
            else:
                st.error(response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 추가 중 예외 발생: {e}")
    
    st.subheader("데이터 조회")
    if st.button("데이터 조회 요청"):
        try:
            url = join_url(API_URL, "get-data")
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.json(response.json())
            else:
                st.error(response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 조회 중 예외 발생: {e}")

# --- 탭 5: 기타 액션 ---
with tabs[4]:
    st.header("기타 액션")
    additional_tabs = st.tabs(["Discord 봇", "RP 이벤트", "게임 상태", "성장 피드백", "개인화 업데이트", "대화 백업", "DB 백업"])
    
    with additional_tabs[0]:
        st.subheader("Discord 봇 통합 (플레이스홀더)")
        discord_command = st.text_input("명령어 입력", key="discord_command")
        if st.button("Discord 명령 실행"):
            try:
                url = join_url(API_URL, "discord-bot")
                params = {"command": discord_command}
                response = requests.get(url, params=params, headers=get_auth_headers())
                if response.status_code == 200:
                    st.success(response.json().get("message", "명령 처리 성공"))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"Discord 봇 명령 실행 중 예외 발생: {e}")
    
    with additional_tabs[1]:
        st.subheader("RP 이벤트 생성 (플레이스홀더)")
        rp_event_input = st.text_input("이벤트 입력", key="rp_event")
        if st.button("RP 이벤트 생성"):
            try:
                url = join_url(API_URL, "rp-event")
                response = requests.post(url, json={"event": rp_event_input}, headers=get_auth_headers())
                if response.status_code == 200:
                    st.success(response.json().get("message", "이벤트 생성 성공"))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"RP 이벤트 생성 중 예외 발생: {e}")
    
    with additional_tabs[2]:
        st.subheader("게임 상태 조회 (플레이스홀더)")
        if st.button("게임 상태 조회"):
            try:
                url = join_url(API_URL, "game-status")
                response = requests.get(url, headers=get_auth_headers())
                if response.status_code == 200:
                    st.json(response.json())
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"게임 상태 조회 중 예외 발생: {e}")
    
    with additional_tabs[3]:
        st.subheader("성장 피드백")
        fb_user = st.text_input("사용자 이름", key="fb_user")
        fb_feedback = st.text_area("피드백 내용", key="fb_feedback")
        if st.button("피드백 저장"):
            try:
                url = join_url(API_URL, "growth-feedback")
                payload = {"user": fb_user, "feedback": fb_feedback}
                response = requests.post(url, json=payload, headers=get_auth_headers())
                if response.status_code == 200:
                    st.success(response.json().get("message", "피드백 저장 성공"))
                    st.info(response.json().get("feedback", ""))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"피드백 저장 중 예외 발생: {e}")
    
    with additional_tabs[4]:
        st.subheader("개인화 업데이트")
        up_user = st.text_input("사용자 이름", key="up_user")
        up_preferences = st.text_area("선호도 설정", key="up_preferences")
        if st.button("개인화 업데이트 요청"):
            try:
                url = join_url(API_URL, "update-personalization")
                payload = {"user": up_user, "preferences": up_preferences}
                response = requests.post(url, json=payload, headers=get_auth_headers())
                if response.status_code == 200:
                    st.success(response.json().get("message", "개인화 업데이트 성공"))
                    st.info(response.json().get("preferences", ""))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"개인화 업데이트 중 예외 발생: {e}")
    
    with additional_tabs[5]:
        st.subheader("대화 내용 백업")
        backup_user = st.text_input("사용자 ID", key="backup_user")
        backup_query = st.text_input("질문 내용", key="backup_query")
        backup_response = st.text_area("응답 내용", key="backup_response")
        if st.button("대화 백업 요청"):
            try:
                url = join_url(API_URL, "backup-memory")
                payload = {"user_id": backup_user, "query": backup_query, "response": backup_response}
                response = requests.post(url, json=payload, headers=get_auth_headers())
                if response.status_code == 200:
                    st.success(response.json().get("message", "백업 성공"))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"대화 백업 중 예외 발생: {e}")
    
    with additional_tabs[6]:
        st.subheader("DB 백업")
        if st.button("DB 백업 요청"):
            try:
                url = join_url(API_URL, "backup-db")
                response = requests.get(url, headers=get_auth_headers())
                if response.status_code == 200:
                    st.success(response.json().get("message", "DB 백업 성공"))
                    st.info(response.json().get("message", ""))
                else:
                    st.error(response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"DB 백업 중 예외 발생: {e}")
