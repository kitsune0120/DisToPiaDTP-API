import streamlit as st
import requests

# 실제 백엔드 주소 (Render 배포 주소 등)
API_URL = "https://distopiadtp-api.onrender.com"

# URL 결합 헬퍼 함수
def join_url(*parts):
    return "/".join(part.strip("/") for part in parts if part)

st.set_page_config(page_title="DisToPia 통합 클라이언트", layout="wide")
st.title("DisToPia 통합 클라이언트")

# 세션 상태에 토큰 저장
if "token" not in st.session_state:
    st.session_state["token"] = None

def get_auth_headers():
    if st.session_state["token"]:
        return {"Authorization": f"Bearer {st.session_state['token']}"}
    return {}

# 탭 구성: 로그인, DB 관리, 파일 관리, AI 대화, 노래 생성, 기타 기능
tabs = st.tabs(["로그인", "DB 관리", "파일 관리", "AI 대화", "노래 생성", "기타 기능"])

# 탭 1: 로그인
with tabs[0]:
    st.header("로그인 (JWT 토큰 발급)")
    username = st.text_input("아이디", key="login_username")
    password = st.text_input("비밀번호", type="password", key="login_password")
    if st.button("로그인"):
        data = {"username": username, "password": password}
        try:
            url = join_url(API_URL, "login-for-access-token")
            response = requests.post(url, json=data)
            if response.status_code == 200:
                token = response.json().get("access_token")
                if token:
                    st.session_state["token"] = token
                    st.success("로그인 성공! 토큰이 저장되었습니다.")
                else:
                    st.error("로그인 실패: 토큰이 없습니다.")
            else:
                detail = response.json().get("detail", "오류 발생")
                st.error(f"로그인 실패: {detail}")
        except Exception as e:
            st.error(f"로그인 중 예외 발생: {e}")
    if st.session_state["token"]:
        st.info(f"현재 토큰: {st.session_state['token']}")
    else:
        st.warning("로그인되지 않았습니다.")

# 탭 2: DB 관리
with tabs[1]:
    st.header("DB 관리")
    if st.button("테이블 생성"):
        try:
            url = join_url(API_URL, "create-table")
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "테이블 생성 완료"))
            else:
                st.error("테이블 생성 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"테이블 생성 중 예외 발생: {e}")

    st.subheader("데이터 추가")
    add_name = st.text_input("이름", key="add_name")
    add_desc = st.text_area("설명", key="add_desc")
    if st.button("데이터 추가"):
        try:
            url = join_url(API_URL, "add-data")
            params = {"name": add_name, "description": add_desc}
            response = requests.post(url, params=params, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "데이터 추가 성공"))
            else:
                st.error("데이터 추가 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 추가 중 예외 발생: {e}")

    st.subheader("데이터 조회")
    if st.button("데이터 조회"):
        try:
            url = join_url(API_URL, "get-data")
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                data = response.json().get("data", [])
                if data:
                    st.write(data)
                else:
                    st.info("데이터가 없습니다.")
            else:
                st.error("데이터 조회 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 조회 중 예외 발생: {e}")

# 탭 3: 파일 관리
with tabs[2]:
    st.header("파일 관리")
    st.subheader("파일 업로드")
    uploaded_file = st.file_uploader("파일 선택 (ZIP, 이미지, 텍스트 등)", type=["zip", "png", "jpg", "jpeg", "pdf", "docx", "txt"], key="file_upload")
    if uploaded_file and st.button("파일 업로드"):
        try:
            url = join_url(API_URL, "upload")
            files = {"file": uploaded_file}
            with st.spinner("파일 업로드 중..."):
                response = requests.post(url, files=files, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(f"업로드 성공: {response.json().get('filename', '')}")
            else:
                st.error(f"업로드 실패: {response.json().get('detail', '오류 발생')}")
        except Exception as e:
            st.error(f"파일 업로드 중 예외 발생: {e}")

    st.subheader("파일 다운로드")
    download_filename = st.text_input("다운로드할 파일명", key="download_filename")
    if download_filename and st.button("파일 다운로드"):
        try:
            url = join_url(API_URL, "download", download_filename)
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.download_button(label="다운로드", data=response.content, file_name=download_filename)
            else:
                st.error("파일 다운로드 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"파일 다운로드 중 예외 발생: {e}")

# 탭 4: AI 대화 (GPT 액션)
with tabs[3]:
    st.header("AI 대화")
    chat_query = st.text_input("질문 입력", key="chat_query")
    chat_history = st.text_area("대화 기록 (옵션, 줄바꿈으로 구분)", key="chat_history")
    if st.button("질문하기"):
        if chat_query:
            try:
                url = join_url(API_URL, "chat")
                history_list = [line for line in chat_history.splitlines() if line] if chat_history else []
                payload = {"query": chat_query, "history": history_list}
                response = requests.post(url, json=payload, headers=get_auth_headers())
                if response.status_code == 200:
                    st.write("응답:", response.json().get("response", "응답 없음"))
                else:
                    st.error("질문 실패: " + response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"질문 중 예외 발생: {e}")
        else:
            st.warning("질문을 입력하세요.")

# 탭 5: 노래 생성
with tabs[4]:
    st.header("노래 생성")
    song_theme = st.text_input("노래 테마 입력", key="song_theme")
    if st.button("가사 생성"):
        if song_theme:
            try:
                url = join_url(API_URL, "generate-lyrics")
                response = requests.post(url, params={"theme": song_theme}, headers=get_auth_headers())
                if response.status_code == 200:
                    st.write("가사:", response.json().get("lyrics", "가사 없음"))
                else:
                    st.error("가사 생성 실패: " + response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"가사 생성 중 예외 발생: {e}")
        else:
            st.warning("테마를 입력하세요.")
    if st.button("노래 생성"):
        if song_theme:
            try:
                url = join_url(API_URL, "generate-song")
                response = requests.post(url, params={"theme": song_theme}, headers=get_auth_headers())
                if response.status_code == 200:
                    st.write("노래 생성 결과:")
                    st.json(response.json().get("song", {}))
                else:
                    st.error("노래 생성 실패: " + response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"노래 생성 중 예외 발생: {e}")
        else:
            st.warning("테마를 입력하세요.")

# 탭 6: 기타 기능
with tabs[5]:
    st.header("기타 기능")
    st.subheader("Discord 봇 명령")
    discord_cmd = st.text_input("Discord 봇 명령어 입력", key="discord_cmd")
    if st.button("명령 실행"):
        try:
            url = join_url(API_URL, "discord-bot")
            response = requests.get(url, params={"command": discord_cmd}, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "성공"))
            else:
                st.error("Discord 명령 실행 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"Discord 명령 실행 중 예외 발생: {e}")
            
    st.subheader("RP 이벤트 생성")
    rp_event_text = st.text_input("RP 이벤트 내용 입력", key="rp_event_text")
    if st.button("이벤트 생성"):
        try:
            url = join_url(API_URL, "rp-event")
            response = requests.post(url, params={"event": rp_event_text}, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "이벤트 생성 성공"))
            else:
                st.error("RP 이벤트 생성 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"RP 이벤트 생성 중 예외 발생: {e}")
            
    st.subheader("게임 상태 조회")
    if st.button("게임 상태 확인"):
        try:
            url = join_url(API_URL, "game-status")
            response = requests.get(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.write("게임 상태:", response.json().get("game_status", {}))
            else:
                st.error("게임 상태 조회 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"게임 상태 조회 중 예외 발생: {e}")
