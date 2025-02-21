import streamlit as st
import requests

# -------------------------------
# 1) 환경 설정
# -------------------------------
# 여기에 본인의 실제 백엔드 주소를 입력하세요.
# 예: "https://distopiadtp-api.onrender.com"
API_URL = "https://your-domain.com"

# Streamlit 페이지 기본 설정
st.set_page_config(page_title="DisToPia 통합 클라이언트", layout="wide")
st.title("DisToPia 통합 클라이언트")

# 인증 토큰을 저장하기 위한 session_state
if "token" not in st.session_state:
    st.session_state["token"] = None

def get_auth_headers():
    """
    세션 스테이트에 토큰이 있다면, 헤더에 Bearer 토큰을 추가해 반환합니다.
    """
    if st.session_state["token"]:
        return {"Authorization": f"Bearer {st.session_state['token']}"}
    return {}

# -------------------------------
# 2) 탭 구성
# -------------------------------
tabs = st.tabs([
    "로그인",       # /login-for-access-token
    "DB 관리",     # /create-table, /add-data, /get-data, /update-data, /delete-data
    "파일 관리",   # /upload/, /get-data, /download/{filename}
    "AI 대화",     # /chat
    "노래 생성",   # /generate-lyrics/, /generate-song/
    "기타 기능"    # /discord-bot, /rp-event, /game-status
])

# -------------------------------------------------------
# 탭 1: 로그인 (POST /login-for-access-token)
# -------------------------------------------------------
with tabs[0]:
    st.header("로그인 (JWT 토큰 발급)")
    username = st.text_input("아이디", key="login_username")
    password = st.text_input("비밀번호", type="password", key="login_password")
    
    if st.button("로그인"):
        data = {"username": username, "password": password}
        try:
            response = requests.post(f"{API_URL}/login-for-access-token", json=data)
            if response.status_code == 200:
                token = response.json().get("access_token")
                if token:
                    st.session_state["token"] = token
                    st.success("로그인 성공! 토큰을 세션에 저장했습니다.")
                else:
                    st.error("로그인 실패: 토큰이 없습니다.")
            else:
                detail = response.json().get("detail", "오류 발생")
                st.error(f"로그인 실패: {detail}")
        except Exception as e:
            st.error(f"로그인 중 예외 발생: {e}")

    if st.session_state["token"]:
        st.info(f"현재 저장된 토큰: {st.session_state['token']}")
    else:
        st.warning("아직 로그인되지 않았습니다. (토큰 없음)")

# -------------------------------------------------------
# 탭 2: DB 관리 (테이블 생성, 데이터 추가/조회/수정/삭제)
# -------------------------------------------------------
with tabs[1]:
    st.header("DB 관리")

    # (1) 테이블 생성
    if st.button("테이블 생성"):
        try:
            response = requests.get(f"{API_URL}/create-table", headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "테이블 생성 완료"))
            else:
                st.error("테이블 생성 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"테이블 생성 중 예외 발생: {e}")

    # (2) 데이터 추가
    st.subheader("데이터 추가")
    add_name = st.text_input("이름", key="add_name")
    add_desc = st.text_area("설명", key="add_desc")
    if st.button("데이터 추가"):
        params = {"name": add_name, "description": add_desc}
        try:
            response = requests.post(f"{API_URL}/add-data", params=params, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "데이터 추가 성공"))
            else:
                st.error("데이터 추가 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 추가 중 예외 발생: {e}")

    # (3) 데이터 조회
    st.subheader("데이터 조회")
    if st.button("데이터 조회"):
        try:
            response = requests.get(f"{API_URL}/get-data", headers=get_auth_headers())
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

    # (4) 데이터 수정
    st.subheader("데이터 수정")
    update_id = st.text_input("수정할 데이터 ID", key="update_id")
    update_name = st.text_input("새 이름", key="update_name")
    update_desc = st.text_area("새 설명", key="update_desc")
    if st.button("데이터 수정"):
        url = f"{API_URL}/update-data/{update_id}"
        params = {"name": update_name, "description": update_desc}
        try:
            response = requests.put(url, params=params, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "데이터 수정 성공"))
            else:
                st.error("데이터 수정 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 수정 중 예외 발생: {e}")

    # (5) 데이터 삭제
    st.subheader("데이터 삭제")
    delete_id = st.text_input("삭제할 데이터 ID", key="delete_id")
    if st.button("데이터 삭제"):
        url = f"{API_URL}/delete-data/{delete_id}"
        try:
            response = requests.delete(url, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "데이터 삭제 성공"))
            else:
                st.error("데이터 삭제 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"데이터 삭제 중 예외 발생: {e}")

# -------------------------------------------------------
# 탭 3: 파일 관리 (업로드, 목록 조회, 다운로드)
# -------------------------------------------------------
with tabs[2]:
    st.header("파일 관리")

    # 파일 업로드
    st.subheader("파일 업로드")
    uploaded_file = st.file_uploader("동영상, 사진, 문서 파일 업로드", 
                                     type=["zip", "png", "jpg", "jpeg", "mp4", "avi"], key="file_upload")
    if uploaded_file:
        if st.button("파일 업로드"):
            with st.spinner("파일 업로드 중..."):
                files = {"file": uploaded_file}
                try:
                    response = requests.post(f"{API_URL}/upload/", files=files, headers=get_auth_headers())
                    if response.status_code == 200:
                        st.success(f"업로드 성공: {response.json().get('filename', '')}")
                    else:
                        st.error(f"업로드 실패: {response.json().get('detail', '오류 발생')}")
                except Exception as e:
                    st.error(f"파일 업로드 중 예외 발생: {e}")

    # 파일 목록 조회
    st.subheader("파일 목록 조회")
    if st.button("파일 목록 새로고침"):
        try:
            # 백엔드에서 파일 목록은 /get-data로 조회한다고 가정
            response = requests.get(f"{API_URL}/get-data", headers=get_auth_headers())
            if response.status_code == 200:
                file_list = response.json().get("data", [])
                if file_list:
                    for file in file_list:
                        file_url = f"{API_URL}/download/{file}"
                        st.markdown(f"**{file}**")
                        ext = file.split(".")[-1].lower()
                        if ext in ["png", "jpg", "jpeg"]:
                            st.image(file_url, width=200)
                        elif ext in ["mp4", "avi"]:
                            st.video(file_url)
                        else:
                            st.markdown(f"[다운로드 링크]({file_url})")
                        st.markdown("---")
                else:
                    st.info("업로드된 파일이 없습니다.")
            else:
                st.error("파일 목록 조회 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"파일 목록 조회 중 예외 발생: {e}")

# -------------------------------------------------------
# 탭 4: AI 대화 (POST /chat)
# -------------------------------------------------------
with tabs[3]:
    st.header("AI 대화")
    question = st.text_input("질문 입력", key="chat_question")
    if st.button("질문하기", key="ask"):
        if question:
            payload = {"query": question, "history": []}
            try:
                response = requests.post(f"{API_URL}/chat", json=payload, headers=get_auth_headers())
                if response.status_code == 200:
                    st.write("응답:", response.json().get("response", "응답 없음"))
                else:
                    st.error("질문 실패: " + response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"질문 중 예외 발생: {e}")
        else:
            st.warning("질문을 입력하세요.")

# -------------------------------------------------------
# 탭 5: 노래 생성 (POST /generate-lyrics/, /generate-song/)
# -------------------------------------------------------
with tabs[4]:
    st.header("노래 생성")
    theme = st.text_input("노래 테마 입력", key="song_theme")

    if st.button("가사 생성", key="generate_lyrics"):
        if theme:
            try:
                # theme을 params로 넘기거나, body(json)로 넘길 수 있음. 여기서는 params 사용 예시
                response = requests.post(f"{API_URL}/generate-lyrics/", params={"theme": theme}, headers=get_auth_headers())
                if response.status_code == 200:
                    st.write("가사:", response.json().get("lyrics", "가사 없음"))
                else:
                    st.error("가사 생성 실패: " + response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"가사 생성 중 예외 발생: {e}")
        else:
            st.warning("테마를 입력하세요.")

    if st.button("노래 생성", key="generate_song"):
        if theme:
            try:
                response = requests.post(f"{API_URL}/generate-song/", params={"theme": theme}, headers=get_auth_headers())
                if response.status_code == 200:
                    song = response.json().get("song", {})
                    st.write("노래 생성 결과:")
                    st.json(song)
                else:
                    st.error("노래 생성 실패: " + response.json().get("detail", "오류 발생"))
            except Exception as e:
                st.error(f"노래 생성 중 예외 발생: {e}")
        else:
            st.warning("테마를 입력하세요.")

# -------------------------------------------------------
# 탭 6: 기타 기능 (GET /discord-bot, POST /rp-event, GET /game-status)
# -------------------------------------------------------
with tabs[5]:
    st.header("기타 기능")

    # 1) Discord 봇 명령
    st.subheader("Discord 봇 명령")
    discord_command = st.text_input("Discord 봇에 보낼 명령어", key="discord_command")
    if st.button("명령 실행", key="execute_discord"):
        try:
            response = requests.get(f"{API_URL}/discord-bot", params={"command": discord_command}, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "성공"))
            else:
                st.error("Discord 명령 실행 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"Discord 명령 실행 중 예외 발생: {e}")

    # 2) RP 이벤트 생성
    st.subheader("RP 이벤트 생성")
    rp_event_text = st.text_input("RP 이벤트 입력", key="rp_event")
    if st.button("이벤트 생성", key="create_rp_event"):
        try:
            response = requests.post(f"{API_URL}/rp-event", params={"event": rp_event_text}, headers=get_auth_headers())
            if response.status_code == 200:
                st.success(response.json().get("message", "이벤트 생성 성공"))
            else:
                st.error("RP 이벤트 생성 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"RP 이벤트 생성 중 예외 발생: {e}")

    # 3) 게임 상태 조회
    st.subheader("게임 상태 조회")
    if st.button("게임 상태 확인", key="game_status"):
        try:
            response = requests.get(f"{API_URL}/game-status", headers=get_auth_headers())
            if response.status_code == 200:
                st.write("게임 상태:", response.json().get("game_status", {}))
            else:
                st.error("게임 상태 조회 실패: " + response.json().get("detail", "오류 발생"))
        except Exception as e:
            st.error(f"게임 상태 조회 중 예외 발생: {e}")
