"""FastMCP 서버의 inputSchema를 확인"""
import asyncio
import httpx
import json


async def main():
    async with httpx.AsyncClient() as client:
        # MCP 서버에 tools/list 요청
        response = await client.post(
            "http://127.0.0.1:8010/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        data = response.json()

        if "result" in data and "tools" in data["result"]:
            for tool in data["result"]["tools"]:
                if tool["name"] == "create_memo":
                    print("create_memo tool:")
                    print(json.dumps(tool, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
