<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DisToPia API Frontend</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
</head>
<body>
    <div class="container mt-5">
        <h1 class="text-center">DisToPia API</h1>
        
        <!-- 파일 업로드 섹션 -->
        <div class="mb-3">
            <h4>파일 업로드</h4>
            <input type="file" id="fileUpload" class="form-control" />
            <button id="uploadBtn" class="btn btn-primary mt-3">파일 업로드</button>
        </div>

        <!-- 업로드된 파일 다운로드 -->
        <div class="mb-3">
            <h4>파일 다운로드</h4>
            <input type="text" id="fileName" class="form-control" placeholder="다운로드할 파일 이름" />
            <button id="downloadBtn" class="btn btn-success mt-3">파일 다운로드</button>
        </div>

        <!-- 데이터베이스 내용 조회 및 수정 -->
        <div class="mb-3">
            <h4>데이터베이스 조회 및 수정</h4>
            <input type="text" id="dataSearch" class="form-control" placeholder="데이터 검색" />
            <button id="searchBtn" class="btn btn-info mt-3">검색</button>
            <ul id="dataList" class="mt-3"></ul>
        </div>

        <!-- GPT 대화창 -->
        <div class="mb-3">
            <h4>GPT-4 대화</h4>
            <textarea id="gptQuery" class="form-control" placeholder="질문을 입력하세요"></textarea>
            <button id="sendQuery" class="btn btn-warning mt-3">질문 전송</button>
            <div id="gptResponse" class="mt-3"></div>
        </div>
        
        <!-- 디스코드 봇 명령어 -->
        <div class="mb-3">
            <h4>디스코드 봇 명령</h4>
            <input type="text" id="discordCommand" class="form-control" placeholder="명령어 입력" />
            <button id="sendDiscordCommand" class="btn btn-secondary mt-3">명령 전송</button>
            <div id="discordResponse" class="mt-3"></div>
        </div>

        <!-- 시스템 상태 조회 -->
        <div class="mb-3">
            <h4>시스템 상태</h4>
            <button id="getSystemStatus" class="btn btn-dark mt-3">시스템 상태 조회</button>
            <div id="systemStatus" class="mt-3"></div>
        </div>

    </div>

    <script>
        // 업로드 버튼 클릭 시
        document.getElementById('uploadBtn').addEventListener('click', function() {
            const fileInput = document.getElementById('fileUpload');
            const file = fileInput.files[0];
            const formData = new FormData();
            formData.append('file', file);

            axios.post('https://127.0.0.1:8001/upload-zip/', formData, {  // 엔드포인트 수정
                headers: {
                    'Content-Type': 'multipart/form-data',
                }
            })
            .then(response => {
                alert("파일 업로드 성공");
            })
            .catch(error => {
                alert("파일 업로드 실패");
            });
        });

        // 다운로드 버튼 클릭 시
        document.getElementById('downloadBtn').addEventListener('click', function() {
            const fileName = document.getElementById('fileName').value;
            axios.get(`https://127.0.0.1:8001/download/${fileName}`, {  // 엔드포인트 수정
                responseType: 'blob',
            })
            .then(response => {
                const link = document.createElement('a');
                link.href = URL.createObjectURL(response.data);
                link.download = fileName;
                link.click();
            })
            .catch(error => {
                alert("파일 다운로드 실패");
            });
        });

        // 데이터베이스에서 데이터 검색
        document.getElementById('searchBtn').addEventListener('click', function() {
            const searchText = document.getElementById('dataSearch').value;
            axios.get(`https://127.0.0.1:8001/get-category/${searchText}`)  // 엔드포인트 수정
            .then(response => {
                const dataList = document.getElementById('dataList');
                dataList.innerHTML = '';
                response.data.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = `${item.filename}: ${item.content}`;
                    dataList.appendChild(li);
                });
            })
            .catch(error => {
                alert("데이터 검색 실패");
            });
        });

        // GPT 대화 보내기
        document.getElementById('sendQuery').addEventListener('click', function() {
            const query = document.getElementById('gptQuery').value;
            axios.post('https://127.0.0.1:8001/chat', { query: query })  // 엔드포인트 수정
            .then(response => {
                document.getElementById('gptResponse').textContent = response.data.response;
            })
            .catch(error => {
                alert("GPT-4 호출 실패");
            });
        });

        // 디스코드 봇 명령어 보내기
        document.getElementById('sendDiscordCommand').addEventListener('click', function() {
            const command = document.getElementById('discordCommand').value;
            axios.get(`https://127.0.0.1:8001/discord-bot?command=${command}`)  // 엔드포인트 수정
            .then(response => {
                document.getElementById('discordResponse').textContent = response.data.message;
            })
            .catch(error => {
                alert("디스코드 명령 처리 실패");
            });
        });

        // 시스템 상태 조회
        document.getElementById('getSystemStatus').addEventListener('click', function() {
            axios.get('https://127.0.0.1:8001/game-status')  // 엔드포인트 수정
            .then(response => {
                document.getElementById('systemStatus').textContent = `Players: ${response.data.game_status.players}, Score: ${response.data.game_status.score}, Status: ${response.data.game_status.status}`;
            })
            .catch(error => {
                alert("게임 상태 조회 실패");
            });
        });
    </script>
</body>
</html>
