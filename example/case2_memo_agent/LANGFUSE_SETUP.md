# LangFuse 통합 가이드

이 가이드는 메모 에이전트에 LangFuse를 통합하여 LLM 호출을 추적하고 디버깅하는 방법을 설명합니다.

## 1. LangFuse란?

LangFuse는 LLM 애플리케이션의 관찰성(observability)을 제공하는 오픈소스 플랫폼입니다. 다음을 추적할 수 있습니다:

- **LLM 호출**: 입력 프롬프트, 출력, 토큰 사용량
- **Tool 호출**: LLM이 어떤 tool을 어떤 매개변수로 호출했는지
- **실행 추적**: 전체 대화 흐름과 latency
- **비용 분석**: 토큰 사용량 기반 비용 계산

## 2. LangFuse 계정 생성

### 옵션 A: Cloud 버전 사용 (권장)

1. [https://cloud.langfuse.com](https://cloud.langfuse.com)에 접속
2. 계정 생성 (GitHub 또는 이메일로 가입)
3. 프로젝트 생성
4. Settings > API Keys에서 키 발급
   - Public Key
   - Secret Key

### 옵션 B: Self-hosted 버전

Docker Compose로 로컬에 설치:

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up -d
```

기본 URL: `http://localhost:3000`

## 3. 환경 변수 설정

`.env` 파일에 다음 값을 추가하세요:

```bash
# LangFuse Observability
LANGFUSE_HOST=https://cloud.langfuse.com  # 또는 self-hosted URL
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx
```

**중요**: `.env` 파일은 절대 git에 커밋하지 마세요!

## 4. 패키지 설치

```bash
cd /home/gomsonixx/Workspace/f-lab-study/example/case2_memo_agent
uv sync
```

## 5. 실행 및 테스트

### 5-1. FastAPI 백엔드 실행

```bash
cd /home/gomsonixx/Workspace/f-lab-study/fastapi-example
uvicorn app.main:app --reload
```

### 5-2. MCP 서버 실행

```bash
cd /home/gomsonixx/Workspace/f-lab-study/example/case2_memo_agent
uv run python memo_mcp_server.py
```

### 5-3. 메모 에이전트 실행

```bash
cd /home/gomsonixx/Workspace/f-lab-study/example/case2_memo_agent
uv run python memo_agent.py
```

정상적으로 실행되면 다음과 같은 메시지가 출력됩니다:

```
✅ LangFuse 통합 활성화 (host: https://cloud.langfuse.com)
✅ LangGraph 메모 에이전트가 준비되었습니다.
```

## 6. LangFuse에서 디버깅하기

### 6-1. 메모 생성 테스트

에이전트에 다음과 같이 요청해보세요:

```
사용자> 제목이 "LangFuse 테스트"인 메모를 생성해줘
```

### 6-2. LangFuse 대시보드에서 확인

1. [https://cloud.langfuse.com](https://cloud.langfuse.com)에 로그인
2. 프로젝트 선택
3. **Traces** 메뉴 클릭
4. 최신 trace 클릭하여 상세 정보 확인

여기서 다음을 확인할 수 있습니다:

#### Tool Call 매개변수 확인
- LLM이 `create_memo` tool을 어떤 매개변수로 호출했는지
- `MemoCreateRequest` 객체가 어떻게 구성되었는지
- JSON 형식으로 전체 입력/출력 확인

#### 예상 출력 예시

```json
{
  "name": "create_memo",
  "arguments": {
    "request": {
      "title": "LangFuse 테스트",
      "description": null,
      "completed": false
    }
  }
}
```

또는 LLM이 잘못된 형식으로 전달한 경우:

```json
{
  "name": "create_memo",
  "arguments": {
    "title": "LangFuse 테스트",
    "description": null,
    "completed": false
  }
}
```

### 6-3. 문제 진단

LangFuse를 통해 다음을 확인할 수 있습니다:

1. **LLM이 tool을 올바르게 호출했는가?**
   - Arguments 구조가 `MemoCreateRequest`와 일치하는지
   - 필드 이름이 정확한지 (`title`, `description`, `completed`)

2. **Validation 오류가 발생했는가?**
   - Tool 실행 결과에서 Pydantic validation 에러 메시지 확인
   - 어떤 필드에서 문제가 발생했는지 파악

3. **Latency 문제는 없는가?**
   - 각 단계별 실행 시간 측정
   - 병목 지점 식별

## 7. Pydantic 방식으로 되돌린 코드

이제 `memo_mcp_server.py`의 `create_memo` 함수가 다시 Pydantic 방식을 사용합니다:

```python
@mcp.tool()
async def create_memo(request: MemoCreateRequest) -> Dict[str, Any]:
    """새 메모 생성"""

    print("\n📝 메모 생성")
    print(f"   title='{request.title}'")
    print(f"   description='{request.description}'")
    print(f"   completed={request.completed}")

    try:
        payload = request.model_dump(exclude_unset=False)
        response = await _request("POST", "/todos/", json=payload)
        memo = response.json()
        print(f"   ✅ 메모 생성 완료 (id={memo.get('id')})")
        return {
            "success": True,
            "memo": memo,
        }
    except httpx.HTTPStatusError as error:
        return _http_error("메모 생성", error)
    except httpx.RequestError as error:
        return _request_error("메모 생성", error)
    except Exception as error:
        return _unexpected_error("메모 생성", error)
```

## 8. 트러블슈팅

### LangFuse 초기화 실패

```
⚠️  LangFuse 초기화 실패: ...
```

- API 키가 올바른지 확인
- `LANGFUSE_HOST` URL이 정확한지 확인
- 네트워크 연결 확인

### 데이터가 LangFuse에 나타나지 않음

- 에이전트 종료 시 `flush()` 호출 확인 (이미 구현됨)
- API 키 권한 확인
- Cloud 버전의 경우 프로젝트가 올바른지 확인

### Tool Call이 여전히 실패함

1. LangFuse에서 정확한 arguments 구조 확인
2. FastMCP가 Pydantic 모델을 어떻게 JSON Schema로 변환하는지 확인:
   ```python
   # 디버깅용 코드 추가
   import json
   print(json.dumps(MemoCreateRequest.model_json_schema(), indent=2))
   ```
3. LLM 모델을 더 강력한 모델로 변경해보기:
   ```bash
   OPENAI_MODEL=gpt-4o  # .env에서 변경
   ```

## 9. 다음 단계

### Tool Description 개선

LLM이 tool을 더 잘 이해할 수 있도록 description을 명확하게 작성:

```python
@mcp.tool()
async def create_memo(request: MemoCreateRequest) -> Dict[str, Any]:
    """새 메모를 생성합니다.

    Args:
        request: MemoCreateRequest 객체로 다음 필드를 포함합니다:
            - title (str, 필수): 메모 제목 (1-100자)
            - description (str, 선택): 메모 내용 (최대 500자)
            - completed (bool, 선택): 완료 여부 (기본값: false)

    Returns:
        Dict with success status and created memo details
    """
```

### 프롬프트 개선

`memo_agent.py`의 시스템 프롬프트에 tool 사용 예시 추가:

```python
def _build_system_prompt(tool_map: Dict[str, BaseTool]) -> str:
    # ... 기존 코드 ...
    return (
        # ... 기존 프롬프트 ...
        "\n\n도구 사용 예시:\n"
        "- 메모 생성 시: create_memo tool에 MemoCreateRequest 객체 전달\n"
        "  예: {\"request\": {\"title\": \"제목\", \"description\": \"내용\", \"completed\": false}}\n"
    )
```

## 10. 참고 자료

- [LangFuse 공식 문서](https://langfuse.com/docs)
- [LangChain Integration](https://langfuse.com/docs/integrations/langchain/tracing)
- [FastMCP 문서](https://github.com/jlowin/fastmcp)
