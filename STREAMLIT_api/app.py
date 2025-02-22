<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DisToPia API 프론트엔드</title>
  <style>
    body {
      font-family: Arial, sans-serif;
    }
    .container {
      width: 80%;
      margin: 0 auto;
    }
    button {
      padding: 10px;
      font-size: 16px;
      cursor: pointer;
    }
    .response {
      margin-top: 20px;
      padding: 10px;
      background-color: #f4f4f4;
      border: 1px solid #ddd;
    }
    #file-upload-form {
      margin-top: 20px;
    }
    #progress-bar-container {
      width: 100%;
      height: 20px;
      background-color: #f3f3f3;
      margin-top: 10px;
    }
    #progress-bar {
      width: 0%;
      height: 100%;
      background-color: green;
    }
    .hidden {
      display: none;
    }
    .spinner {
      border: 8px solid #f3f3f3;
      border-top: 8px solid #3498db;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 2s linear infinite;
      margin-top: 20px;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>

<div class="container">
  <h1>DisToPia API 인터페이스</h1>

  <!-- 로그인 -->
  <h2>로그인</h2>
  <form id="login-form">
    <label for="username">사용자 이름:</label>
    <input type="text" id="username" name="username" required><br><br>
    <label for="password">비밀번호:</label>
    <input type="password" id="password" name="password" required><br><br>
    <button type="submit">로그인</button>
  </form>
  <div id="login-response" class="response"></div>

  <!-- 파일 업로드 -->
  <h2>파일 업로드</h2>
  <form id="file-upload-form" enctype="multipart/form-data">
    <input type="file" id="file" name="file" multiple required><br><br>
    <button type="submit">파일 업로드</button>
    <div id="progress-bar-container" class="hidden">
      <div id="progress-bar"></div>
    </div>
  </form>
  <div id="file-upload-response" class="response"></div>

  <!-- 대화 -->
  <h2>GPT-4 대화</h2>
  <textarea id="chat-query" rows="4" cols="50" placeholder="질문을 입력하세요..." required></textarea><br><br>
  <button id="chat-submit">대화하기</button>
  <div id="chat-response" class="response"></div>

  <!-- DB 백업 -->
  <h2>DB 백업</h2>
  <button id="backup-db-btn">DB 백업</button>
  <div id="backup-db-response" class="response"></div>

  <!-- 사용자 피드백 -->
  <h2>사용자 피드백</h2>
  <form id="feedback-form">
    <label for="user-feedback">피드백:</label><br>
    <textarea id="user-feedback" rows="4" cols="50" placeholder="피드백을 입력하세요..."></textarea><br><br>
    <button type="submit">피드백 제출</button>
  </form>
  <div id="feedback-response" class="response"></div>
</div>

<script>
  // 로그인 처리
  document.getElementById('login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    const response = await fetch('https://127.0.0.1:8001/login-for-access-token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();
    const loginResponse = document.getElementById('login-response');
    if (response.ok) {
      localStorage.setItem("token", data.access_token); // JWT 토큰 저장
      loginResponse.textContent = `로그인 성공! 토큰: ${data.access_token}`;
    } else {
      loginResponse.textContent = `로그인 실패: ${data.detail}`;
    }
  });

  // 파일 업로드 처리
  document.getElementById('file-upload-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const fileInput = document.getElementById('file');
    const formData = new FormData();
    for (let file of fileInput.files) {
      formData.append('file', file);
    }

    const progressBar = document.getElementById('progress-bar');
    const progressContainer = document.getElementById('progress-bar-container');
    progressContainer.classList.remove('hidden');

    const response = await fetch('https://127.0.0.1:8001/upload/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: formData
    });

    if (response.ok) {
      progressBar.style.width = '100%';
      const data = await response.json();
      document.getElementById('file-upload-response').textContent = `파일 업로드 성공: ${data.filename}`;
    } else {
      document.getElementById('file-upload-response').textContent = '파일 업로드 실패';
    }
  });

  // GPT-4 대화 처리
  document.getElementById('chat-submit').addEventListener('click', async () => {
    const query = document.getElementById('chat-query').value;
    const history = []; // 히스토리 추가 가능

    const response = await fetch('https://127.0.0.1:8001/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ query, history })
    });

    const data = await response.json();
    const chatResponse = document.getElementById('chat-response');
    if (response.ok) {
      chatResponse.textContent = `GPT 응답: ${data.response}`;
    } else {
      chatResponse.textContent = `대화 오류: ${data.detail}`;
    }
  });

  // DB 백업 처리
  document.getElementById('backup-db-btn').addEventListener('click', async () => {
    const response = await fetch('https://127.0.0.1:8001/backup-db', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    const data = await response.json();
    document.getElementById('backup-db-response').textContent = response.ok ? `DB 백업 성공! 파일 위치: ${data.message}` : `DB 백업 실패: ${data.error}`;
  });

  // 사용자 피드백 처리
  document.getElementById('feedback-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const feedback = document.getElementById('user-feedback').value;

    const response = await fetch('https://127.0.0.1:8001/growth-feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ user: "anonymous", feedback })
    });

    const data = await response.json();
    document.getElementById('feedback-response').textContent = `피드백 저장 성공: ${data.feedback}`;
  });
</script>

</body>
</html>
