<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>DisToPia API Frontend</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .section { border: 1px solid #ccc; padding: 15px; margin-bottom: 20px; }
    .section h2 { margin-top: 0; }
    input, textarea { width: 100%; margin: 5px 0; padding: 5px; }
    button { margin: 5px 0; padding: 5px 10px; }
    pre { background: #f8f8f8; padding: 10px; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>DisToPia API Frontend</h1>

  <!-- 루트 엔드포인트 -->
  <div class="section" id="root-section">
    <h2>루트 엔드포인트 (GET /)</h2>
    <button onclick="callRoot()">호출</button>
    <pre id="root-result"></pre>
  </div>

  <!-- 로그인 -->
  <div class="section" id="login-section">
    <h2>로그인 (POST /login-for-access-token)</h2>
    <input type="text" id="login-username" placeholder="사용자 아이디">
    <input type="password" id="login-password" placeholder="비밀번호">
    <button onclick="login()">로그인</button>
    <pre id="login-result"></pre>
  </div>

  <!-- 테이블 생성 -->
  <div class="section" id="create-table-section">
    <h2>테이블 생성 (GET /create-table)</h2>
    <button onclick="createTable()">생성</button>
    <pre id="create-table-result"></pre>
  </div>

  <!-- 데이터 추가 -->
  <div class="section" id="add-data-section">
    <h2>데이터 추가 (POST /add-data)</h2>
    <input type="text" id="add-data-name" placeholder="데이터 이름">
    <textarea id="add-data-description" placeholder="데이터 설명"></textarea>
    <button onclick="addData()">추가</button>
    <pre id="add-data-result"></pre>
  </div>

  <!-- 데이터 조회 -->
  <div class="section" id="get-data-section">
    <h2>데이터 조회 (GET /get-data)</h2>
    <button onclick="getData()">조회</button>
    <pre id="get-data-result"></pre>
  </div>

  <!-- 데이터 업데이트 -->
  <div class="section" id="update-data-section">
    <h2>데이터 업데이트 (PUT /update-data/{data_id})</h2>
    <input type="number" id="update-data-id" placeholder="데이터 ID">
    <input type="text" id="update-data-name" placeholder="새 이름">
    <textarea id="update-data-description" placeholder="새 설명"></textarea>
    <button onclick="updateData()">업데이트</button>
    <pre id="update-data-result"></pre>
  </div>

  <!-- 데이터 삭제 -->
  <div class="section" id="delete-data-section">
    <h2>데이터 삭제 (DELETE /delete-data/{data_id})</h2>
    <input type="number" id="delete-data-id" placeholder="데이터 ID">
    <button onclick="deleteData()">삭제</button>
    <pre id="delete-data-result"></pre>
  </div>

  <!-- 파일 업로드 -->
  <div class="section" id="file-upload-section">
    <h2>파일 업로드 (POST /upload/)</h2>
    <input type="file" id="upload-file">
    <button onclick="uploadFile()">업로드</button>
    <pre id="upload-file-result"></pre>
  </div>

  <!-- 파일 다운로드 -->
  <div class="section" id="file-download-section">
    <h2>파일 다운로드 (GET /download/{filename})</h2>
    <input type="text" id="download-filename" placeholder="파일 이름">
    <button onclick="downloadFile()">다운로드</button>
    <pre id="download-file-result"></pre>
  </div>

  <!-- 파일 삭제 -->
  <div class="section" id="file-delete-section">
    <h2>파일 삭제 (DELETE /delete-file/{filename})</h2>
    <input type="text" id="delete-filename" placeholder="파일 이름">
    <button onclick="deleteFile()">삭제</button>
    <pre id="delete-file-result"></pre>
  </div>

  <!-- 대화 API -->
  <div class="section" id="chat-section">
    <h2>대화 API (POST /chat)</h2>
    <input type="text" id="chat-query" placeholder="질문 입력">
    <textarea id="chat-history" placeholder="이전 대화 (쉼표로 구분)"></textarea>
    <button onclick="chat()">대화 시작</button>
    <pre id="chat-result"></pre>
  </div>

  <!-- 디스코드 봇 -->
  <div class="section" id="discord-bot-section">
    <h2>디스코드 봇 명령 (GET /discord-bot)</h2>
    <input type="text" id="discord-command" placeholder="명령어 입력 (예: ping)">
    <button onclick="discordBotCommand()">실행</button>
    <pre id="discord-bot-result"></pre>
  </div>

  <!-- RP 이벤트 생성 -->
  <div class="section" id="rp-event-section">
    <h2>RP 이벤트 생성 (POST /rp-event)</h2>
    <input type="text" id="rp-event" placeholder="이벤트 이름">
    <button onclick="rpEvent()">생성</button>
    <pre id="rp-event-result"></pre>
  </div>

  <!-- 게임 상태 조회 -->
  <div class="section" id="game-status-section">
    <h2>게임 상태 조회 (GET /game-status)</h2>
    <button onclick="gameStatus()">조회</button>
    <pre id="game-status-result"></pre>
  </div>

  <!-- 성장형 피드백 -->
  <div class="section" id="growth-feedback-section">
    <h2>성장형 피드백 (POST /growth-feedback)</h2>
    <input type="text" id="feedback-user" placeholder="사용자 이름">
    <textarea id="feedback-content" placeholder="피드백 내용"></textarea>
    <button onclick="growthFeedback()">제출</button>
    <pre id="growth-feedback-result"></pre>
  </div>

  <!-- 개인화 업데이트 -->
  <div class="section" id="update-personalization-section">
    <h2>개인화 업데이트 (POST /update-personalization)</h2>
    <input type="text" id="personal-user" placeholder="사용자 이름">
    <textarea id="personal-preferences" placeholder="선호 설정 내용"></textarea>
    <button onclick="updatePersonalization()">업데이트</button>
    <pre id="update-personalization-result"></pre>
  </div>

  <!-- 대화 내용 백업 -->
  <div class="section" id="backup-memory-section">
    <h2>대화 내용 백업 (POST /backup-memory)</h2>
    <input type="text" id="backup-user-id" placeholder="사용자 ID">
    <input type="text" id="backup-query" placeholder="사용자 질문">
    <textarea id="backup-response" placeholder="GPT 응답"></textarea>
    <button onclick="backupMemory()">백업</button>
    <pre id="backup-memory-result"></pre>
  </div>

  <!-- DB 백업 -->
  <div class="section" id="backup-db-section">
    <h2>DB 백업 (GET /backup-db)</h2>
    <button onclick="backupDB()">백업 실행</button>
    <pre id="backup-db-result"></pre>
  </div>

  <!-- Actions.json 조회 -->
  <div class="section" id="actions-json-section">
    <h2>Actions.json 조회 (GET /actions.json)</h2>
    <button onclick="getActionsJson()">조회</button>
    <pre id="actions-json-result"></pre>
  </div>

  <!-- OpenAPI.json 조회 -->
  <div class="section" id="openapi-json-section">
    <h2>OpenAPI.json 조회 (GET /openapi.json)</h2>
    <button onclick="getOpenapiJson()">조회</button>
    <pre id="openapi-json-result"></pre>
  </div>

  <script>
    const API_BASE = "http://127.0.0.1:8000";
    let accessToken = "";

    async function callApi(endpoint, method = "GET", body = null, requiresAuth = false) {
      const headers = { "Content-Type": "application/json" };
      if (requiresAuth && accessToken) {
        headers["Authorization"] = "Bearer " + accessToken;
      }
      const options = { method, headers };
      if (body) {
        options.body = JSON.stringify(body);
      }
      try {
        const res = await fetch(API_BASE + endpoint, options);
        return await res.json();
      } catch (error) {
        return { error: error.toString() };
      }
    }

    async function callRoot() {
      const result = await callApi("/");
      document.getElementById("root-result").textContent = JSON.stringify(result, null, 2);
    }

    async function login() {
      const username = document.getElementById("login-username").value;
      const password = document.getElementById("login-password").value;
      const result = await callApi("/login-for-access-token", "POST", { username, password });
      if (result.access_token) {
        accessToken = result.access_token;
      }
      document.getElementById("login-result").textContent = JSON.stringify(result, null, 2);
    }

    async function createTable() {
      const result = await callApi("/create-table");
      document.getElementById("create-table-result").textContent = JSON.stringify(result, null, 2);
    }

    async function addData() {
      const name = document.getElementById("add-data-name").value;
      const description = document.getElementById("add-data-description").value;
      const result = await callApi("/add-data", "POST", { name, description }, true);
      document.getElementById("add-data-result").textContent = JSON.stringify(result, null, 2);
    }

    async function getData() {
      const result = await callApi("/get-data");
      document.getElementById("get-data-result").textContent = JSON.stringify(result, null, 2);
    }

    async function updateData() {
      const dataId = document.getElementById("update-data-id").value;
      const name = document.getElementById("update-data-name").value;
      const description = document.getElementById("update-data-description").value;
      const result = await callApi(`/update-data/${dataId}`, "PUT", { data_id: parseInt(dataId), name, description }, true);
      document.getElementById("update-data-result").textContent = JSON.stringify(result, null, 2);
    }

    async function deleteData() {
      const dataId = document.getElementById("delete-data-id").value;
      const result = await callApi(`/delete-data/${dataId}`, "DELETE", null, true);
      document.getElementById("delete-data-result").textContent = JSON.stringify(result, null, 2);
    }

    async function uploadFile() {
      const fileInput = document.getElementById("upload-file");
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      try {
        const res = await fetch(API_BASE + "/upload/", {
          method: "POST",
          body: formData,
          headers: accessToken ? { "Authorization": "Bearer " + accessToken } : {}
        });
        const result = await res.json();
        document.getElementById("upload-file-result").textContent = JSON.stringify(result, null, 2);
      } catch (error) {
        document.getElementById("upload-file-result").textContent = error.toString();
      }
    }

    async function downloadFile() {
      const filename = document.getElementById("download-filename").value;
      try {
        const res = await fetch(API_BASE + `/download/${filename}`);
        if (res.ok) {
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          a.click();
          document.getElementById("download-file-result").textContent = "파일 다운로드 시작됨.";
        } else {
          const errorData = await res.json();
          document.getElementById("download-file-result").textContent = JSON.stringify(errorData, null, 2);
        }
      } catch (error) {
        document.getElementById("download-file-result").textContent = error.toString();
      }
    }

    async function deleteFile() {
      const filename = document.getElementById("delete-filename").value;
      const result = await callApi(`/delete-file/${filename}`, "DELETE", null, true);
      document.getElementById("delete-file-result").textContent = JSON.stringify(result, null, 2);
    }

    async function chat() {
      const query = document.getElementById("chat-query").value;
      const historyText = document.getElementById("chat-history").value;
      const history = historyText.split(",").map(s => s.trim()).filter(s => s.length > 0);
      const result = await callApi("/chat", "POST", { query, history });
      document.getElementById("chat-result").textContent = JSON.stringify(result, null, 2);
    }

    async function discordBotCommand() {
      const command = document.getElementById("discord-command").value;
      const result = await callApi(`/discord-bot?command=${encodeURIComponent(command)}`);
      document.getElementById("discord-bot-result").textContent = JSON.stringify(result, null, 2);
    }

    async function rpEvent() {
      const eventName = document.getElementById("rp-event").value;
      const result = await callApi("/rp-event", "POST", { event: eventName });
      document.getElementById("rp-event-result").textContent = JSON.stringify(result, null, 2);
    }

    async function gameStatus() {
      const result = await callApi("/game-status");
      document.getElementById("game-status-result").textContent = JSON.stringify(result, null, 2);
    }

    async function growthFeedback() {
      const user = document.getElementById("feedback-user").value;
      const feedback = document.getElementById("feedback-content").value;
      const result = await callApi("/growth-feedback", "POST", { user, feedback });
      document.getElementById("growth-feedback-result").textContent = JSON.stringify(result, null, 2);
    }

    async function updatePersonalization() {
      const user = document.getElementById("personal-user").value;
      const preferences = document.getElementById("personal-preferences").value;
      const result = await callApi("/update-personalization", "POST", { user, preferences });
      document.getElementById("update-personalization-result").textContent = JSON.stringify(result, null, 2);
    }

    async function backupMemory() {
      const user_id = document.getElementById("backup-user-id").value;
      const query = document.getElementById("backup-query").value;
      const responseText = document.getElementById("backup-response").value;
      const result = await callApi("/backup-memory", "POST", { user_id, query, response: responseText });
      document.getElementById("backup-memory-result").textContent = JSON.stringify(result, null, 2);
    }

    async function backupDB() {
      const result = await callApi("/backup-db");
      document.getElementById("backup-db-result").textContent = JSON.stringify(result, null, 2);
    }

    async function getActionsJson() {
      const result = await callApi("/actions.json");
      document.getElementById("actions-json-result").textContent = JSON.stringify(result, null, 2);
    }

    async function getOpenapiJson() {
      const result = await callApi("/openapi.json");
      document.getElementById("openapi-json-result").textContent = JSON.stringify(result, null, 2);
    }
  </script>
</body>
</html>
