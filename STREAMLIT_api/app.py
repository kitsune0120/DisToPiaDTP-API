<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DisToPia API 프론트엔드</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
        }
        .button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
        }
        .button:hover {
            background-color: #45a049;
        }
        pre {
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h1>DisToPia API와의 상호작용</h1>

    <h2>사용자 로그인</h2>
    <form id="loginForm">
        <input type="text" id="username" placeholder="아이디" required>
        <input type="password" id="password" placeholder="비밀번호" required>
        <button type="submit" class="button">로그인</button>
    </form>

    <h2>데이터 추가</h2>
    <form id="addDataForm">
        <input type="text" id="name" placeholder="이름" required>
        <input type="text" id="description" placeholder="설명" required>
        <button type="submit" class="button">데이터 추가</button>
    </form>

    <h2>파일 업로드</h2>
    <form id="uploadFileForm" enctype="multipart/form-data">
        <input type="file" id="file" required>
        <button type="submit" class="button">파일 업로드</button>
    </form>

    <h2>데이터 조회</h2>
    <button id="fetchDataButton" class="button">데이터 조회</button>
    <pre id="dataOutput"></pre>

    <h2>DB 백업</h2>
    <button id="backupDataButton" class="button">DB 백업</button>
    <pre id="backupOutput"></pre>

    <script>
        let accessToken = null;

        // 사용자 로그인
        document.getElementById('loginForm').addEventListener('submit', async function(event) {
            event.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            const response = await fetch('/login-for-access-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password })
            });

            const result = await response.json();
            if (response.ok) {
                accessToken = result.access_token;
                alert('로그인 성공');
            } else {
                alert('로그인 실패: ' + result.detail);
            }
        });

        // 데이터 추가
        document.getElementById('addDataForm').addEventListener('submit', async function(event) {
            event.preventDefault();
            const name = document.getElementById('name').value;
            const description = document.getElementById('description').value;

            const response = await fetch('/add-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify({ name, description })
            });

            const result = await response.json();
            alert(result.message);
        });

        // 파일 업로드
        document.getElementById('uploadFileForm').addEventListener('submit', async function(event) {
            event.preventDefault();
            const formData = new FormData();
            formData.append('file', document.getElementById('file').files[0]);

            const response = await fetch('/upload/', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                },
                body: formData
            });

            const result = await response.json();
            alert(result.message);
        });

        // 데이터 조회
        document.getElementById('fetchDataButton').addEventListener('click', async function() {
            const response = await fetch('/get-data', {
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });
            const data = await response.json();
            document.getElementById('dataOutput').textContent = JSON.stringify(data, null, 2);
        });

        // DB 백업
        document.getElementById('backupDataButton').addEventListener('click', async function() {
            const response = await fetch('/backup-db', {
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });
            const result = await response.json();
            document.getElementById('backupOutput').textContent = result.message;
        });
    </script>
</body>
</html>
