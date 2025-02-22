{
  "version": "1.0",
  "actions": [
    {
      "name": "root",
      "description": "루트 엔드포인트: 기본 테스트 라우트",
      "endpoint": "/",
      "method": "GET",
      "parameters": {}
    },
    {
      "name": "login",
      "description": "사용자 로그인 및 JWT 토큰 발급",
      "endpoint": "/login-for-access-token",
      "method": "POST",
      "parameters": {
        "username": {
          "type": "string",
          "description": "사용자 아이디"
        },
        "password": {
          "type": "string",
          "description": "사용자 비밀번호"
        }
      }
    },
    {
      "name": "createTable",
      "description": "DB 테이블 생성 (dtp_data, conversation)",
      "endpoint": "/create-table",
      "method": "GET",
      "parameters": {}
    },
    {
      "name": "addData",
      "description": "데이터 추가 (dtp_data 테이블)",
      "endpoint": "/add-data",
      "method": "POST",
      "parameters": {
        "name": {
          "type": "string",
          "description": "데이터 이름"
        },
        "description": {
          "type": "string",
          "description": "데이터 설명"
        }
      }
    },
    {
      "name": "getData",
      "description": "데이터 조회 (dtp_data 테이블)",
      "endpoint": "/get-data",
      "method": "GET",
      "parameters": {}
    },
    {
      "name": "updateData",
      "description": "데이터 업데이트 (ID 기준)",
      "endpoint": "/update-data/{data_id}",
      "method": "PUT",
      "parameters": {
        "data_id": {
          "type": "number",
          "description": "업데이트할 데이터의 ID"
        },
        "name": {
          "type": "string",
          "description": "새 이름"
        },
        "description": {
          "type": "string",
          "description": "새 설명"
        }
      }
    },
    {
      "name": "deleteData",
      "description": "데이터 삭제 (ID 기준)",
      "endpoint": "/delete-data/{data_id}",
      "method": "DELETE",
      "parameters": {
        "data_id": {
          "type": "number",
          "description": "삭제할 데이터의 ID"
        }
      }
    },
    {
      "name": "uploadFile",
      "description": "파일 업로드 및 분석/DB 저장",
      "endpoint": "/upload/",
      "method": "POST",
      "parameters": {
        "file": {
          "type": "string",
          "format": "binary",
          "description": "업로드할 파일 (multipart/form-data)"
        }
      }
    },
    {
      "name": "downloadFile",
      "description": "파일 다운로드",
      "endpoint": "/download/{filename}",
      "method": "GET",
      "parameters": {
        "filename": {
          "type": "string",
          "description": "다운로드할 파일 이름"
        }
      }
    },
    {
      "name": "deleteFile",
      "description": "파일 삭제",
      "endpoint": "/delete-file/{filename}",
      "method": "DELETE",
      "parameters": {
        "filename": {
          "type": "string",
          "description": "삭제할 파일 이름"
        }
      }
    },
    {
      "name": "chat",
      "description": "대화 API: GPT-4를 활용한 대화 기능",
      "endpoint": "/chat",
      "method": "POST",
      "parameters": {
        "query": {
          "type": "string",
          "description": "사용자 질문"
        },
        "history": {
          "type": "array",
          "description": "이전 대화 히스토리",
          "items": {
            "type": "string"
          }
        }
      }
    },
    {
      "name": "discordBotCommand",
      "description": "Discord 봇 명령 테스트",
      "endpoint": "/discord-bot",
      "method": "GET",
      "parameters": {
        "command": {
          "type": "string",
          "description": "봇 명령어 (예: ping)"
        }
      }
    },
    {
      "name": "rpEvent",
      "description": "RP 이벤트 생성",
      "endpoint": "/rp-event",
      "method": "POST",
      "parameters": {
        "event": {
          "type": "string",
          "description": "생성할 이벤트 이름"
        }
      }
    },
    {
      "name": "gameStatus",
      "description": "게임 상태 조회",
      "endpoint": "/game-status",
      "method": "GET",
      "parameters": {}
    },
    {
      "name": "growthFeedback",
      "description": "성장형 피드백 저장",
      "endpoint": "/growth-feedback",
      "method": "POST",
      "parameters": {
        "user": {
          "type": "string",
          "description": "사용자 이름"
        },
        "feedback": {
          "type": "string",
          "description": "피드백 내용"
        }
      }
    },
    {
      "name": "updatePersonalization",
      "description": "사용자 개인화 설정 업데이트",
      "endpoint": "/update-personalization",
      "method": "POST",
      "parameters": {
        "user": {
          "type": "string",
          "description": "사용자 이름"
        },
        "preferences": {
          "type": "string",
          "description": "선호 설정 내용"
        }
      }
    },
    {
      "name": "backupMemory",
      "description": "대화 내용 백업",
      "endpoint": "/backup-memory",
      "method": "POST",
      "parameters": {
        "user_id": {
          "type": "string",
          "description": "사용자 ID"
        },
        "query": {
          "type": "string",
          "description": "사용자 입력"
        },
        "response": {
          "type": "string",
          "description": "GPT 응답"
        }
      }
    },
    {
      "name": "backupDB",
      "description": "DB 백업",
      "endpoint": "/backup-db",
      "method": "GET",
      "parameters": {}
    }
  ]
}
