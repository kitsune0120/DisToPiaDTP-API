<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>DisToPia API Frontend</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .container { max-width: 800px; margin: 0 auto; }
    .section { margin-bottom: 40px; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
    label { display: block; margin-top: 10px; }
    input[type="text"], input[type="password"], textarea { width: 100%; padding: 8px; box-sizing: border-box; }
    button { margin-top: 10px; padding: 8px 16px; }
    .output { margin-top: 10px; background: #f4f4f4; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>DisToPia API 프론트엔드</h1>

    <!-- 로그인 섹션 -->
    <div class="section" id="login-section">
      <h2>로그인</h2>
      <label for="username">아이디:</label>
      <input type="text" id="username" placeholder="아이디 입력" />
      <label for="password">비밀번호:</label>
      <input type="password" id="password" placeholder="비밀번호 입력" />
      <button onclick="login()">로그인</button>
      <div id="login-output" class="output"></div>
    </div>

    <!-- 대화 섹션 -->
    <div class="section" id="chat-section">
      <h2>대화하기</h2>
      <label for="chat-query">질문:</label>
      <input type="text" id="chat-query" placeholder="질문 입력" />
      <button onclick="sendChat()">전송</button>
      <div id="chat-output" class="output"></div>
    </div>

    <!-- 파일 업로드 섹션 -->
    <div class="section" id="upload-section">
      <h2>파일 업로드</h2>
      <input type="file" id="file-input" />
      <button onclick="uploadFile()">업로드</button>
      <div id="upload-output" class="output"></div>
    </div>

    <!-- 게임 상태 조회 섹션 -->
    <div class="section" id="game-status-section">
      <h2>게임 상태 조회</h2>
      <button onclick="getGameStatus()">상태 확인</button>
      <div id="game-status-output" class="output"></div>
    </div>
  </div>

  <script>
    let token = '';

    // 로그인 함수: /login-for-access-token 엔드포인트 호출
    async function login() {
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      try {
        const response = await fetch('/login-for-access-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        if (response.ok) {
          token = data.access_token;
          document.getElementById('login-output').innerText = '로그인 성공! 토큰: ' + token;
        } else {
          document.getElementById('login-output').innerText = '로그인 실패: ' + data.detail;
        }
      } catch (error) {
        document.getElementById('login-output').innerText = '에러 발생: ' + error;
      }
    }

    // 대화 함수: /chat 엔드포인트 호출
    async function sendChat() {
      const query = document.getElementById('chat-query').value;
      try {
        const response = await fetch('/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': 'Bearer ' + token })
          },
          body: JSON.stringify({ query, history: [] })
        });
        const data = await response.json();
        if (response.ok) {
          document.getElementById('chat-output').innerText = '응답: ' + data.response;
        } else {
          document.getElementById('chat-output').innerText = '에러: ' + JSON.stringify(data);
        }
      } catch (error) {
        document.getElementById('chat-output').innerText = '에러 발생: ' + error;
      }
    }

    // 파일 업로드 함수: /upload/ 엔드포인트 호출
    async function uploadFile() {
      const fileInput = document.getElementById('file-input');
      if (fileInput.files.length === 0) {
        alert('업로드할 파일을 선택해주세요.');
        return;
      }
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      try {
        const response = await fetch('/upload/', {
          method: 'POST',
          headers: {
            ...(token && { 'Authorization': 'Bearer ' + token })
          },
          body: formData
        });
        const data = await response.json();
        if (response.ok) {
          document.getElementById('upload-output').innerText = '업로드 성공: ' + data.message;
        } else {
          document.getElementById('upload-output').innerText = '업로드 실패: ' + JSON.stringify(data);
        }
      } catch (error) {
        document.getElementById('upload-output').innerText = '에러 발생: ' + error;
      }
    }

    // 게임 상태 조회 함수: /game-status 엔드포인트 호출
    async function getGameStatus() {
      try {
        const response = await fetch('/game-status');
        const data = await response.json();
        if (response.ok) {
          document.getElementById('game-status-output').innerText = '게임 상태: ' + JSON.stringify(data.game_status);
        } else {
          document.getElementById('game-status-output').innerText = '에러: ' + JSON.stringify(data);
        }
      } catch (error) {
        document.getElementById('game-status-output').innerText = '에러 발생: ' + error;
      }
    }
  </script>
</body>
</html>
