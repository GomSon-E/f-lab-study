# LangFuse + Pydantic MCP 서버 통합 가이드

이 문서는 FastMCP 서버에서 Pydantic 모델을 사용하면서 LangFuse로 LLM 디버깅을 하는 과정에서 발생한 문제와 해결 방법을 상세히 설명합니다.

## 목차

1. [문제 상황](#문제-상황)
2. [핵심 개념](#핵심-개념)
3. [문제 분석](#문제-분석)
4. [해결 과정](#해결-과정)
5. [최종 해결책](#최종-해결책)
6. [학습 포인트](#학습-포인트)

---

## 문제 상황

### 초기 상태

LLM이 잘못된 출력을 생성하여 `create_memo` tool 호출이 실패했습니다. Pydantic 방식을 사용하고 싶었지만 오류가 발생했습니다.

**작동하지 않는 코드:**
```python
@mcp.tool()
async def create_memo(request: MemoCreateRequest) -> Dict[str, Any]:
    """새 메모 생성"""
    # Pydantic 모델로 매개변수를 받음
    ...
```

**오류 내용:**
- LLM이 개별 필드(`title`, `description`, `completed`)를 전달
- MCP 서버는 `request` 객체를 기대
- 매개변수 미스매치로 인한 실행 실패

### 목표

1. ✅ **Pydantic 모델 사용 유지**: 타입 안정성과 검증 유지
2. ✅ **LangFuse로 디버깅**: LLM의 tool call 매개변수 추적
3. ✅ **정상 동작**: tool이 올바르게 실행되어야 함

---

## 핵심 개념

### 1. JSON Schema와 $ref

**JSON Schema**는 JSON 데이터의 구조를 정의하는 표준입니다.

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "age": {"type": "integer"}
  },
  "required": ["title"]
}
```

**$ref (Reference)**는 schema 내에서 다른 정의를 참조하는 방법입니다:

```json
{
  "$defs": {
    "Person": {
      "type": "object",
      "properties": {
        "name": {"type": "string"}
      }
    }
  },
  "properties": {
    "person": {
      "$ref": "#/$defs/Person"  // Person 정의 참조
    }
  }
}
```

**왜 사용하나요?**
- 중복 제거: 같은 구조를 여러 번 정의하지 않음
- 재사용성: 한 번 정의한 schema를 여러 곳에서 참조
- 유지보수: 한 곳만 수정하면 모든 참조가 업데이트됨

### 2. FastMCP의 Pydantic → JSON Schema 변환

FastMCP는 Pydantic 모델을 MCP tool schema로 변환할 때, **단일 `request` 매개변수로 래핑**합니다.

**Pydantic 모델:**
```python
class MemoCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False

@mcp.tool()
async def create_memo(request: MemoCreateRequest):
    ...
```

**FastMCP가 생성하는 JSON Schema:**
```json
{
  "type": "object",
  "properties": {
    "request": {
      "$ref": "#/$defs/MemoCreateRequest"  // 중첩된 구조!
    }
  },
  "required": ["request"],
  "$defs": {
    "MemoCreateRequest": {
      "type": "object",
      "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 100},
        "description": {"type": "string", "maxLength": 500},
        "completed": {"type": "boolean", "default": false}
      },
      "required": ["title"]
    }
  }
}
```

**핵심 포인트:**
- `request` 매개변수 안에 모든 필드가 중첩됨
- LLM은 이 구조를 보고 다음과 같이 호출해야 함:
  ```json
  {
    "request": {
      "title": "제목",
      "description": "내용",
      "completed": false
    }
  }
  ```

### 3. LangChain의 Tool Schema 변환

LangChain은 MCP tool을 OpenAI function calling 형식으로 변환합니다.

**문제점:**
- `$ref`를 자동으로 resolve하려고 시도
- 중첩된 구조를 flat하게 펼침
- LLM에게 전달되는 schema가 변형됨

**결과:**
```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},      // flat하게 풀림!
    "description": {"type": "string"},
    "completed": {"type": "boolean"}
  },
  "required": ["title"]
}
```

LLM은 이 schema를 보고 다음과 같이 호출:
```json
{
  "title": "제목",
  "description": "내용",
  "completed": false
}
```

**미스매치 발생:**
- LLM: flat arguments 전달
- MCP 서버: nested `request` 객체 기대
- → 실행 실패!

### 4. OpenAI Function Calling

OpenAI API는 LLM이 함수를 호출할 수 있도록 함수 정의를 제공합니다.

**함수 정의 형식:**
```json
{
  "name": "create_memo",
  "description": "새 메모 생성",
  "parameters": {
    "type": "object",
    "properties": {
      "title": {"type": "string", "description": "메모 제목"},
      "description": {"type": "string"}
    },
    "required": ["title"]
  }
}
```

**LLM의 함수 호출:**
```json
{
  "name": "create_memo",
  "arguments": {
    "title": "회의 메모",
    "description": "오후 3시 회의"
  }
}
```

**핵심:** LLM은 `parameters` schema를 정확히 따라 `arguments`를 생성합니다.

---

## 문제 분석

### 1단계: MCP 서버의 Schema 확인

**목적:** FastMCP가 실제로 어떤 schema를 제공하는지 확인

**도구:** `test_mcp_schema.py`
```python
tools = await client.get_tools(server_name=server_name)
for tool in tools:
    print(json.dumps(tool.args, indent=2))
```

**결과:**
```json
{
  "request": {
    "$ref": "#/$defs/MemoCreateRequest"
  }
}
```

**분석:**
- FastMCP는 `request` 파라미터로 감싸진 schema 제공
- `$ref`로 실제 정의를 참조
- **예상대로 작동**: Pydantic 모델이 단일 파라미터로 래핑됨

### 2단계: LangChain의 Schema 변환 확인

**목적:** LangChain이 MCP schema를 어떻게 변환하는지 확인

**도구:** `test_fixed_schema.py`
```python
tools = await client.get_tools(server_name=server_name)
for tool in tools:
    print("args_schema:", tool.args_schema)
    print("get_input_schema:", tool.get_input_schema())
```

**결과:**
- `args_schema`: dict 형태 (MCP에서 받은 원본)
- `get_input_schema()`: Pydantic BaseModel 자동 생성
- BaseModel 생성 시 **$ref가 flat하게 펼쳐짐**

**분석:**
- LangChain의 `StructuredTool`은 dict schema를 Pydantic BaseModel로 변환
- 변환 과정에서 중첩 구조가 손실됨
- LLM에게는 flat schema가 전달됨

### 3단계: LLM에 전달되는 Schema 확인

**목적:** OpenAI API에 실제로 전달되는 함수 정의 확인

**도구:** `test_tool_call_schema.py`
```python
llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools)
# llm_with_tools가 OpenAI에 보내는 schema 확인
```

**결과:**
```json
{
  "name": "create_memo",
  "parameters": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "description": {"type": "string"},
      "completed": {"type": "boolean"}
    }
  }
}
```

**분석:**
- `request` 래핑이 제거됨
- LLM은 flat arguments를 직접 전달하도록 학습됨
- **이것이 미스매치의 원인!**

### 4단계: LangFuse에서 확인

**목적:** LLM이 실제로 어떻게 tool을 호출하는지 확인

**LangFuse 대시보드에서 본 내용:**
```json
{
  "name": "create_memo",
  "arguments": {
    "title": "멘토링",
    "description": "오늘 19시에 멘토링",
    "completed": false
  }
}
```

**분석:**
- LLM은 schema대로 flat arguments를 전달
- MCP 서버는 `{"request": {...}}` 형태를 기대
- **예상대로 미스매치 발생**

---

## 해결 과정

### 시도 1: Schema의 $ref를 inline으로 확장

**아이디어:** $ref를 해결하여 LangChain이 제대로 인식하도록 함

**구현:**
```python
def _fix_mcp_tool_schema_attempt1(tool):
    schema = tool.args_schema
    if '$ref' in schema['properties']['request']:
        ref_path = schema['properties']['request']['$ref']
        def_name = ref_path.split('/')[-1]
        # $ref를 실제 정의로 대체
        schema['properties']['request'] = schema['$defs'][def_name]
    return tool
```

**결과:** ❌ 실패
- LangChain의 BaseModel 자동 생성 로직이 여전히 flat하게 펼침
- `get_input_schema()`가 dict schema를 무시하고 자체 모델 생성

**왜 실패했나?**
- `args_schema`는 단순 dict
- LangChain은 dict를 Pydantic BaseModel로 변환할 때 **자체 로직** 사용
- dict 내용을 참고하되, 중첩 구조를 평평하게 만듦

### 시도 2: LLM 호출 시 arguments 래핑

**아이디어:** LLM이 flat arguments를 보내면, agent에서 래핑해서 전달

**구현:**
```python
async def call_tools(state):
    for call in tool_calls:
        tool_args = call.get("args") or {}
        # flat args를 request로 래핑
        if "request" not in tool_args:
            tool_args = {"request": tool_args}
        result = await tool.ainvoke(tool_args)
```

**결과:** ✅ 작동함! 하지만...
- Pydantic 검증이 제대로 작동
- 하지만 사용자가 원한 방식이 아님: "LLM이 애초에 flat하게 전달하지 않도록"

**한계:**
- LLM은 여전히 잘못된 schema를 학습
- Agent가 workaround를 적용하는 것
- 근본적인 해결이 아님

### 시도 3: Schema를 Flat하게 변환 + 래핑 조합

**아이디어:**
1. LLM에게는 flat schema 제공 (쉽게 이해)
2. Agent가 MCP 호출 시 다시 래핑 (Pydantic 검증 유지)

**최종 구현:**
```python
def _fix_mcp_tool_schema(tool: BaseTool) -> BaseTool:
    """
    FastMCP의 nested schema를 flat하게 펼쳐서
    LLM이 직접 필드에 접근하도록 변환
    """
    schema = tool.args_schema.copy()

    if '$defs' in schema and 'properties' in schema:
        props = schema['properties']
        if 'request' in props and '$ref' in props['request']:
            ref_path = props['request']['$ref']
            def_name = ref_path.split('/')[-1]
            if def_name in schema['$defs']:
                request_schema = schema['$defs'][def_name]

                # request의 properties를 최상위로 이동
                schema['properties'] = request_schema.get('properties', {})
                schema['required'] = request_schema.get('required', [])

    tool.args_schema = schema
    return tool
```

**변환 전 schema:**
```json
{
  "properties": {
    "request": {
      "$ref": "#/$defs/MemoCreateRequest"
    }
  },
  "required": ["request"],
  "$defs": {
    "MemoCreateRequest": {
      "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "completed": {"type": "boolean"}
      },
      "required": ["title"]
    }
  }
}
```

**변환 후 schema:**
```json
{
  "properties": {
    "title": {"type": "string"},
    "description": {"type": "string"},
    "completed": {"type": "boolean"}
  },
  "required": ["title"]
}
```

**Agent의 래핑 로직:**
```python
async def call_tools(state):
    for call in tool_calls:
        tool_args = call.get("args") or {}

        # LLM은 flat arguments를 보내므로,
        # MCP 서버를 위해 request로 래핑
        if tool_name in ["create_memo", "update_memo", ...]:
            if "request" not in tool_args:
                tool_args = {"request": tool_args}

        result = await tool.ainvoke(tool_args)
```

**결과:** ✅ 완벽하게 작동!

---

## 최종 해결책

### 아키텍처 다이어그램

```
┌─────────────┐
│   사용자     │
│   요청      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         LangGraph Agent                  │
│  ┌───────────────────────────────────┐  │
│  │  1. Tool Schema 수정              │  │
│  │     _fix_mcp_tool_schema()        │  │
│  │     - request 래핑 제거            │  │
│  │     - properties를 flat하게        │  │
│  └───────────────────────────────────┘  │
│                                          │
│  ┌───────────────────────────────────┐  │
│  │  2. LLM에 Flat Schema 전달        │  │
│  │     bind_tools(tools)             │  │
│  └───────────────────────────────────┘  │
│                                          │
│  ┌───────────────────────────────────┐  │
│  │  3. LLM이 Flat Args 생성          │  │
│  │     {title: "...", ...}           │  │
│  └───────────────────────────────────┘  │
│                                          │
│  ┌───────────────────────────────────┐  │
│  │  4. Agent가 Request로 래핑        │  │
│  │     {request: {title: "...", ...}}│  │
│  └───────────────────────────────────┘  │
└────────────┬─────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│         FastMCP Server                   │
│  ┌───────────────────────────────────┐  │
│  │  5. Pydantic 검증                 │  │
│  │     MemoCreateRequest.validate()  │  │
│  └───────────────────────────────────┘  │
│                                          │
│  ┌───────────────────────────────────┐  │
│  │  6. FastAPI 백엔드 호출           │  │
│  │     POST /todos/                  │  │
│  └───────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### 데이터 흐름

**1. Schema 변환 (Agent 초기화 시)**

```python
# 원본 MCP Schema
{
  "properties": {
    "request": {"$ref": "#/$defs/MemoCreateRequest"}
  }
}

# ↓ _fix_mcp_tool_schema() 적용

# LLM에 전달되는 Schema
{
  "properties": {
    "title": {"type": "string"},
    "description": {"type": "string"},
    "completed": {"type": "boolean"}
  }
}
```

**2. LLM 호출 (런타임)**

```python
# LLM이 생성한 Arguments (Flat)
{
  "title": "멘토링",
  "description": "오늘 19시에 멘토링",
  "completed": false
}

# ↓ Agent의 call_tools()에서 래핑

# MCP 서버에 전달되는 Arguments (Nested)
{
  "request": {
    "title": "멘토링",
    "description": "오늘 19시에 멘토링",
    "completed": false
  }
}
```

**3. Pydantic 검증 (MCP 서버)**

```python
# FastMCP가 자동으로 수행
request = MemoCreateRequest(**tool_args["request"])
# ↓ Pydantic 검증 통과
# - title: 1-100자 검증
# - description: 최대 500자 검증
# - completed: bool 타입 검증
```

### 코드 정리

**1. memo_agent.py - Schema 수정 함수**

```python
def _fix_mcp_tool_schema(tool: BaseTool) -> BaseTool:
    """
    FastMCP의 nested 'request' schema를 flat하게 펼쳐서
    LLM이 직접 호출 가능하도록 변환.

    Before:
    {
      "properties": {
        "request": {"$ref": "#/$defs/MemoCreateRequest"}
      }
    }

    After:
    {
      "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "completed": {"type": "boolean"}
      }
    }
    """
    if not hasattr(tool, 'args_schema') or not isinstance(tool.args_schema, dict):
        return tool

    schema = tool.args_schema.copy()

    if '$defs' in schema and 'properties' in schema:
        props = schema['properties']
        if 'request' in props and '$ref' in props['request']:
            ref_path = props['request']['$ref']
            if ref_path.startswith('#/$defs/'):
                def_name = ref_path.split('/')[-1]
                if def_name in schema['$defs']:
                    request_schema = schema['$defs'][def_name]

                    # request 래핑 제거, 필드를 최상위로
                    schema['properties'] = request_schema.get('properties', {})
                    schema['required'] = request_schema.get('required', [])

                    if 'title' in request_schema:
                        schema['title'] = request_schema['title']
                    if 'description' in request_schema:
                        schema['description'] = request_schema['description']

    tool.args_schema = schema
    return tool
```

**2. memo_agent.py - Tool 호출 시 래핑**

```python
async def call_tools(state: AgentState) -> AgentState:
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None) or []
    outputs: List[ToolMessage] = []

    for call in tool_calls:
        tool_name = call.get("name")
        tool_args = call.get("args") or {}
        tool = tool_map.get(tool_name or "")

        # LLM은 flat arguments를 보내지만,
        # MCP 서버는 request 객체를 기대함
        if tool_name in ["create_memo", "update_memo", "list_memos",
                        "get_memo", "delete_memo"]:
            if "request" not in tool_args:
                tool_args = {"request": tool_args}

        print(f"🛠️  {tool_name} 호출: {_stringify(tool_args)}")
        try:
            result = await tool.ainvoke(tool_args)
            outputs.append(ToolMessage(
                content=_stringify(result),
                tool_call_id=tool_call_id,
            ))
            print(f"✅ {tool_name} 결과: {_stringify(result)}")
        except Exception as exc:
            error_text = f"{tool_name} 실행 중 오류: {exc}"
            outputs.append(ToolMessage(
                content=error_text,
                tool_call_id=tool_call_id
            ))
            print(f"❌ {error_text}")

    return {"messages": outputs}
```

**3. memo_agent.py - Agent 초기화**

```python
async def prepare_agent():
    # ... LangFuse 설정 ...

    client = MultiServerMCPClient({server_name: connection})
    tools = await client.get_tools(server_name=server_name)

    # FastMCP의 nested schema를 flat하게 변환
    tools = [_fix_mcp_tool_schema(tool) for tool in tools]

    tool_map = {tool.name: tool for tool in tools}
    system_prompt = _build_system_prompt(tool_map)

    llm = ChatOpenAI(model=model_name, temperature=0.2)
    graph = _create_graph(llm, tool_map, langfuse_handler)

    return graph, base_state, langfuse_handler
```

**4. memo_mcp_server.py - Pydantic 모델 유지**

```python
class MemoCreateRequest(BaseModel):
    """메모 생성 요청"""
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    completed: bool = Field(False)

@mcp.tool()
async def create_memo(request: MemoCreateRequest) -> Dict[str, Any]:
    """새 메모 생성"""
    print(f"   title='{request.title}'")
    print(f"   description='{request.description}'")
    print(f"   completed={request.completed}")

    try:
        payload = request.model_dump(exclude_unset=False)
        response = await _request("POST", "/todos/", json=payload)
        memo = response.json()
        return {"success": True, "memo": memo}
    except Exception as error:
        return _unexpected_error("메모 생성", error)
```

### LangFuse에서 확인하기

**1. 대시보드 접속**
- URL: https://us.cloud.langfuse.com
- Traces 메뉴 선택

**2. Trace 상세 보기**

**Generation (LLM 호출):**
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "system",
      "content": "너는 메모 관리 조수다..."
    },
    {
      "role": "user",
      "content": "제목이 '멘토링'인 메모를 만들어줘"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "create_memo",
        "description": "새 메모 생성",
        "parameters": {
          "type": "object",
          "properties": {
            "title": {"type": "string", "description": "메모 제목"},
            "description": {"type": "string"},
            "completed": {"type": "boolean"}
          },
          "required": ["title"]
        }
      }
    }
  ]
}
```

**Tool Call (LLM의 응답):**
```json
{
  "name": "create_memo",
  "arguments": {
    "title": "멘토링",
    "description": "오늘 19시에 멘토링",
    "completed": false
  }
}
```

**디버깅 포인트:**
- ✅ LLM이 flat arguments 생성 확인
- ✅ 모든 필드가 올바른 타입으로 전달
- ✅ required 필드 (`title`) 누락 확인 가능
- ✅ 각 tool call의 latency 측정

---

## 학습 포인트

### 1. JSON Schema의 중요성

**교훈:** LLM은 schema를 정확히 따릅니다. Schema가 잘못되면 LLM도 잘못 호출합니다.

**Best Practice:**
- Schema는 가능한 한 단순하게 (flat structure)
- 명확한 description 제공
- required 필드 명시
- 타입과 제약 조건 정확히 정의

### 2. 라이브러리 간 통합의 복잡성

**문제:**
- FastMCP: Pydantic → nested JSON Schema
- LangChain: JSON Schema → Pydantic → flat structure
- OpenAI: flat function parameters 기대

**교훈:**
각 라이브러리의 변환 로직을 이해하고, 필요시 중간에서 조정해야 합니다.

### 3. Adapter Pattern의 활용

우리의 해결책은 사실 **Adapter Pattern**입니다:

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  LLM (Flat)  │ ───> │   Adapter    │ ───> │ MCP (Nested) │
└──────────────┘      └──────────────┘      └──────────────┘
                      Schema 변환 +
                      Arguments 래핑
```

**장점:**
- LLM과 MCP 서버 코드 변경 없음
- 각 컴포넌트가 선호하는 형식 유지
- 유연한 확장 가능

### 4. Observability의 중요성

**LangFuse 없이 디버깅했다면:**
- LLM이 무엇을 전달했는지 모름
- Schema가 어떻게 변환되었는지 추측만 가능
- Trial and error로만 문제 해결

**LangFuse 사용:**
- 정확한 arguments 확인
- Schema와 실제 호출 비교
- 근본 원인 파악 가능

**교훈:**
복잡한 LLM 애플리케이션에서는 observability 툴이 필수입니다.

### 5. Type Safety vs Flexibility

**트레이드오프:**

| 방식 | Type Safety | LLM 호환성 | 복잡도 |
|------|-------------|------------|--------|
| 개별 파라미터 | ❌ 낮음 | ✅ 높음 | ✅ 낮음 |
| Pydantic + Adapter | ✅ 높음 | ✅ 높음 | ⚠️ 중간 |
| Nested Schema | ✅ 높음 | ❌ 낮음 | ✅ 낮음 |

**결론:**
우리는 Type Safety와 LLM 호환성을 모두 얻었지만, 약간의 복잡도를 추가했습니다. 대부분의 프로덕션 환경에서는 이 트레이드오프가 가치 있습니다.

### 6. Python 버전 호환성

**발견:**
- Python 3.14는 아직 많은 라이브러리가 완전히 지원하지 않음
- Pydantic v1이 Python 3.14에서 문제 발생
- LangFuse가 내부적으로 Pydantic v1 사용

**교훈:**
- 프로덕션에서는 안정적인 Python 버전 사용 (3.11-3.13)
- 새 버전 도입 전 의존성 호환성 확인
- `requires-python` constraint로 버전 제한

### 7. 환경 변수 명명 규칙

**LangFuse 통합 시 주의:**
- ❌ `LANGFUSE_BASE_URL` (안 됨)
- ✅ `LANGFUSE_HOST` (정확한 이름)

**교훈:**
라이브러리 문서를 정확히 확인하고, 예제 코드의 환경 변수 이름을 그대로 사용하세요.

---

## 추가 개선 아이디어

### 1. Generic Schema Unwrapper

현재는 tool 이름을 하드코딩했지만, 더 일반적으로 만들 수 있습니다:

```python
def should_unwrap_request(tool_name: str, tool_args: dict) -> bool:
    """request 래핑이 필요한지 자동 감지"""
    # tool의 원본 schema를 확인하여 자동 판단
    return "request" in original_schema and "request" not in tool_args
```

### 2. Pydantic 모델 직접 사용

LangChain이 dict schema 대신 Pydantic 모델을 직접 받도록:

```python
from pydantic import create_model

# dict schema로부터 Pydantic 모델 생성
RequestModel = create_model(
    'RequestModel',
    **{field: (type, ...) for field, type in schema['properties'].items()}
)

tool.args_schema = RequestModel
```

### 3. Custom MCP Adapter

`langchain-mcp-adapters`를 포크하여 커스터마이징:

```python
class PydanticAwareMCPAdapter:
    def convert_tool(self, mcp_tool):
        # FastMCP의 Pydantic 구조를 이해하는 로직
        if self._is_pydantic_wrapped(mcp_tool):
            return self._unwrap_pydantic_tool(mcp_tool)
        return super().convert_tool(mcp_tool)
```

### 4. LangFuse Trace 자동 태깅

디버깅을 더 쉽게:

```python
langfuse_handler = CallbackHandler(
    trace_context={
        "tags": ["memo-agent", "pydantic", "mcp"],
        "metadata": {
            "schema_version": "flat",
            "wrapping_enabled": True
        }
    }
)
```

---

## 참고 자료

### 공식 문서

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [LangChain Tools](https://python.langchain.com/docs/how_to/#tools)
- [LangFuse LangChain Integration](https://langfuse.com/docs/integrations/langchain)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [JSON Schema Specification](https://json-schema.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

### 관련 이슈

- [langchain-mcp-adapters: Schema conversion](https://github.com/langchain-ai/langchain-mcp-adapters/issues)
- [FastMCP: Pydantic model wrapping](https://github.com/jlowin/fastmcp/discussions)

### 코드 예제

- [memo_agent.py](./memo_agent.py) - 최종 구현
- [memo_mcp_server.py](./memo_mcp_server.py) - Pydantic 모델 정의
- [test_fixed_schema.py](./test_fixed_schema.py) - Schema 변환 테스트

---

## 요약

1. **문제**: FastMCP의 Pydantic 모델이 nested schema로 변환되어 LLM과 미스매치
2. **원인**: LangChain이 schema를 flat하게 변환하지만, MCP는 nested 구조 기대
3. **해결**: Schema를 명시적으로 flat하게 변환 + Agent에서 다시 래핑
4. **결과**: Pydantic 검증 유지 + LLM 호환성 확보 + LangFuse로 디버깅 가능

**핵심 교훈:**
- 각 레이어의 schema 변환 과정을 이해하라
- Observability 툴로 실제 동작을 확인하라
- 필요시 adapter 패턴으로 호환성 문제 해결하라
