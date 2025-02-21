import streamlit as st
import requests

# 로컬에서 FastAPI 백엔드를 실행할 때의 기본 URL
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

# 탭 구성: 로그인, 파일 관리, 대화 등 (원하는 기능 추가 가능)
tabs = st.tabs(["로그인", "파일 관리", "대화"])

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
    uploaded_file = st.file_uploader("파일 선택 (ZIP, 이미지, 텍스트 등)", type=["zip", "png", "jpg", "jpeg", "pdf", "docx", "txt"], key="file_upload")
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
