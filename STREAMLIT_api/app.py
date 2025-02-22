<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DisToPia API Frontend</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; }
    input, button { padding: 8px; margin: 5px 0; }
  </style>
</head>
<body>
  <h1>DisToPia API Frontend</h1>
  <div>
    <h2>로그인</h2>
    <input type="text" id="username" placeholder="아이디">
    <input type="password" id="password" placeholder="비밀번호">
    <button onclick="login()">로그인</button>
  </div>

  <div>
    <h2>데이터 추가</h2>
    <input type="text" id="dataName" placeholder="데이터 이름">
    <input type="text" id="dataDescription" placeholder="데이터 설명">
    <button onclick="addData()">데이터 추가</button>
  </div>

  <div>
    <h2>파일 업로드</h2>
    <input type="file" id="fileInput">
    <button onclick="uploadFile()">파일 업로드</button>
  </div>

  <div>
    <h2>대화 요청 (GPT-4)</h2>
    <input type="text" id="chatQuery" placeholder="질문 입력">
    <button onclick="chat()">대화 요청</button>
    <p id="chatResponse"></p>
  </div>

  <script>
    // API 호출 시, 상대 경로를 사용하므로, 백엔드와 같은 도메인에 있으면 HTTPS도 자동 적용됨.
    const apiBase = ""; // 동일 도메인 사용

    async function login() {
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      const res = await fetch(apiBase + "/login-for-access-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem("token", data.access_token);
        alert("로그인 성공!");
      } else {
        alert("로그인 실패: " + data.detail);
      }
    }

    async function addData() {
      const token = localStorage.getItem("token");
      const name = document.getElementById('dataName').value;
      const description = document.getElementById('dataDescription').value;
      const res = await fetch(apiBase + "/add-data", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + token
        },
        body: JSON.stringify({ name, description })
      });
      const data = await res.json();
      alert(data.message);
    }

    async function uploadFile() {
      const token = localStorage.getItem("token");
      const fileInput = document.getElementById('fileInput');
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      const res = await fetch(apiBase + "/upload/", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + token
        },
        body: formData
      });
      const data = await res.json();
      alert(data.message);
    }

    async function chat() {
      const token = localStorage.getItem("token");
      const query = document.getElementById('chatQuery').value;
      const res = await fetch(apiBase + "/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + token
        },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      document.getElementById('chatResponse').innerText = data.response;
    }
  </script>
</body>
</html>
