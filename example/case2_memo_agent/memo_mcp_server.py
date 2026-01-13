"""FastMCP 서버 - FastAPI 메모 앱 HTTP 클라이언트"""
import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, model_validator

load_dotenv()

# MCP 서버 설정
MEMO_MCP_HOST = os.getenv("MEMO_MCP_HOST", "127.0.0.1")
MEMO_MCP_PORT = int(os.getenv("MEMO_MCP_PORT", "8010"))

# BE API 설정
MEMO_BE_API_URL = os.getenv("MEMO_BE_API_URL", "http://127.0.0.1:8000")
MEMO_BE_TIMEOUT = float(os.getenv("MEMO_BE_TIMEOUT", "30"))

mcp = FastMCP(
    "Memo MCP Server",
    host=MEMO_MCP_HOST,
    port=MEMO_MCP_PORT,
)


class MemoListRequest(BaseModel):
    """메모 목록 조회 요청"""

    skip: int = Field(0, ge=0, description="건너뛸 레코드 수")
    limit: int = Field(100, ge=1, le=1000, description="가져올 최대 레코드 수")


class MemoIdRequest(BaseModel):
    """개별 메모 조회/삭제 요청"""

    todo_id: int = Field(..., ge=1, description="메모 ID")


class MemoCreateRequest(BaseModel):
    """메모 생성 요청"""

    title: str = Field(..., min_length=1, max_length=100, description="메모 제목")
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="메모 내용",
    )
    completed: bool = Field(False, description="완료 여부")


class MemoUpdateRequest(BaseModel):
    """메모 수정 요청"""

    todo_id: int = Field(..., ge=1, description="수정할 메모 ID")
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="새 제목",
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="새 설명",
    )
    completed: Optional[bool] = Field(
        None,
        description="완료 여부",
    )

    @model_validator(mode="after")
    def validate_changes(self) -> "MemoUpdateRequest":
        if self.title is None and self.description is None and self.completed is None:
            raise ValueError("최소 한 개 필드를 수정해야 합니다")
        return self


async def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> httpx.Response:
    """공통 HTTP 요청 헬퍼"""
    async with httpx.AsyncClient(
        base_url=MEMO_BE_API_URL,
        timeout=timeout or MEMO_BE_TIMEOUT,
    ) as client:
        response = await client.request(method, path, params=params, json=json)
        response.raise_for_status()
        return response


def _extract_error_detail(response: Optional[httpx.Response]) -> str:
    if response is None:
        return ""
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, list):
                return str(detail[0])
            if detail:
                return str(detail)
            return str(data)
        return str(data)
    except Exception:
        return response.text or ""


def _http_error(action: str, error: httpx.HTTPStatusError) -> Dict[str, Any]:
    detail = _extract_error_detail(error.response)
    message = f"{action} 실패 (HTTP {error.response.status_code})"
    print(f"   ❌ {message} - {detail}")
    return {
        "success": False,
        "error_message": message,
        "detail": detail,
    }


def _request_error(action: str, error: httpx.RequestError) -> Dict[str, Any]:
    message = f"{action} 요청 중 연결 오류: {error}"
    print(f"   ❌ {message}")
    return {
        "success": False,
        "error_message": message,
    }


def _unexpected_error(action: str, error: Exception) -> Dict[str, Any]:
    message = f"{action} 처리 중 예기치 못한 오류"
    print(f"   ❌ {message}: {error}")
    return {
        "success": False,
        "error_message": message,
        "detail": str(error),
    }


@mcp.tool()
async def list_memos(request: MemoListRequest) -> Dict[str, Any]:
    """메모 목록을 조회하는 툴"""

    print("\n📒 메모 목록 조회")
    print(f"   skip={request.skip}, limit={request.limit}")

    try:
        response = await _request(
            "GET",
            "/todos/",
            params={"skip": request.skip, "limit": request.limit},
        )
        memos: List[Dict[str, Any]] = response.json()
        print(f"   ✅ {len(memos)}건 조회")
        return {
            "success": True,
            "memos": memos,
            "count": len(memos),
        }
    except httpx.HTTPStatusError as error:
        return _http_error("메모 목록 조회", error)
    except httpx.RequestError as error:
        return _request_error("메모 목록 조회", error)
    except Exception as error:
        return _unexpected_error("메모 목록 조회", error)


@mcp.tool()
async def get_memo(request: MemoIdRequest) -> Dict[str, Any]:
    """특정 메모를 조회"""

    print("\n🔍 메모 상세 조회")
    print(f"   todo_id={request.todo_id}")

    try:
        response = await _request("GET", f"/todos/{request.todo_id}")
        memo = response.json()
        print(f"   ✅ '{memo.get('title')}' 메모 조회")
        return {
            "success": True,
            "memo": memo,
        }
    except httpx.HTTPStatusError as error:
        return _http_error("메모 조회", error)
    except httpx.RequestError as error:
        return _request_error("메모 조회", error)
    except Exception as error:
        return _unexpected_error("메모 조회", error)


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


@mcp.tool()
async def update_memo(request: MemoUpdateRequest) -> Dict[str, Any]:
    """기존 메모 수정"""

    print("\n✏️  메모 수정")
    print(f"   todo_id={request.todo_id}")

    try:
        payload = request.model_dump(exclude_unset=True)
        todo_id = payload.pop("todo_id")
        response = await _request("PUT", f"/todos/{todo_id}", json=payload)
        memo = response.json()
        print(f"   ✅ 메모 수정 완료 (id={memo.get('id')})")
        return {
            "success": True,
            "memo": memo,
        }
    except httpx.HTTPStatusError as error:
        return _http_error("메모 수정", error)
    except httpx.RequestError as error:
        return _request_error("메모 수정", error)
    except Exception as error:
        return _unexpected_error("메모 수정", error)


@mcp.tool()
async def delete_memo(request: MemoIdRequest) -> Dict[str, Any]:
    """메모 삭제"""

    print("\n🗑️  메모 삭제")
    print(f"   todo_id={request.todo_id}")

    try:
        await _request("DELETE", f"/todos/{request.todo_id}")
        print("   ✅ 삭제 완료")
        return {
            "success": True,
            "deleted_id": request.todo_id,
        }
    except httpx.HTTPStatusError as error:
        return _http_error("메모 삭제", error)
    except httpx.RequestError as error:
        return _request_error("메모 삭제", error)
    except Exception as error:
        return _unexpected_error("메모 삭제", error)


@mcp.tool()
async def check_memo_api_health() -> Dict[str, Any]:
    """메모 API 서버 헬스 체크"""

    print("\n🏥 메모 API 상태 확인")

    try:
        response = await _request("GET", "/health", timeout=10)
        data = response.json()
        print(f"   ✅ 서버 상태: {data.get('status', 'unknown')}")
        return {
            "success": True,
            "server_url": MEMO_BE_API_URL,
            "status": data.get("status", "unknown"),
            "message": data.get("message", "메모 API 서버가 정상 작동 중입니다."),
        }
    except httpx.HTTPStatusError as error:
        return _http_error("헬스 체크", error)
    except httpx.RequestError as error:
        return _request_error("헬스 체크", error)
    except Exception as error:
        return _unexpected_error("헬스 체크", error)


def main() -> None:
    """MCP 서버 시작"""

    print("🚀 Memo MCP Server 시작")
    print(f"   MCP Server: http://{MEMO_MCP_HOST}:{MEMO_MCP_PORT}")
    print(f"   BE API URL: {MEMO_BE_API_URL}")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
