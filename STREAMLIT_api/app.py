import streamlit as st
import requests

# 백엔드 API URL (필요 시 실제 배포 주소로 수정하세요)
API_URL = "https://distopiadtp-api.onrender.com"

# 페이지 기본 설정
st.set_page_config(page_title="DisToPia 미디어 관리", layout="wide")
st.title("DisToPia 미디어 관리")

# 탭 구성: 파일 관리, AI 대화, DB 검색
tabs = st.tabs(["파일 관리", "AI 대화", "DB 검색"])

# -------------------------------------
# 1. 파일 관리 탭
# -------------------------------------
with tabs[0]:
    st.header("파일 관리")
    
    # 파일 업로드 섹션
    st.subheader("파일 업로드")
    uploaded_file = st.file_uploader("동영상, 사진, 문서 파일 업로드", type=["zip", "png", "jpg", "jpeg", "mp4", "avi"])
    if uploaded_file:
        with st.spinner("파일 업로드 중..."):
            files = {"file": uploaded_file}
            response = requests.post(f"{API_URL}/upload/", files=files)
            if response.status_code == 200:
                st.success(f"업로드 성공: {response.json().get('filename', '')}")
            else:
                st.error(f"업로드 실패: {response.json().get('detail', '오류 발생')}")
    
    # 파일 목록 조회 섹션
    st.subheader("업로드된 파일 목록")
    if st.button("파일 목록 새로고침"):
        response = requests.get(f"{API_URL}/files/")
        if response.status_code == 200:
            file_list = response.json().get("files", [])
            if file_list:
                for file in file_list:
                    file_url = f"{API_URL}/download/{file}/"
                    st.markdown(f"**{file}**")
                    # 파일 확장자에 따라 미리보기 제공
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
            st.error("파일 목록을 가져오지 못했습니다.")

# -------------------------------------
# 2. AI 대화 탭
# -------------------------------------
with tabs[1]:
    st.header("AI 대화")
    question = st.text_input("질문을 입력하세요")
    if st.button("질문하기"):
        if question:
            payload = {"question": question}
            response = requests.post(f"{API_URL}/chat/", json=payload)
            if response.status_code == 200:
                st.write("응답:", response.json().get("response", "응답 없음"))
            else:
                st.error("질문 실패: " + response.json().get("detail", "오류 발생"))
        else:
            st.warning("질문 내용을 입력해 주세요.")

# -------------------------------------
# 3. DB 검색 탭
# -------------------------------------
with tabs[2]:
    st.header("DB 검색")
    query = st.text_input("검색할 쿼리를 입력하세요", key="db_search")
    if st.button("검색", key="search_btn"):
        if query:
            params = {"query": query}
            response = requests.get(f"{API_URL}/search/", params=params)
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    st.write("검색 결과:")
                    for res in results:
                        st.write("- ", res)
                else:
                    st.info("검색 결과가 없습니다.")
            else:
                st.error("검색 실패: " + response.json().get("detail", "오류 발생"))
        else:
            st.warning("검색할 쿼리를 입력해 주세요.")
