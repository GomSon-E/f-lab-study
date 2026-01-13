"""MCP 서버의 tool schema를 확인하는 스크립트"""
import asyncio
import os
import json
from typing import cast

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StreamableHttpConnection

load_dotenv()


async def main():
    server_name = os.getenv("MEMO_MCP_SERVER_NAME", "memo")
    host = os.getenv("MEMO_MCP_HOST", "127.0.0.1")
    port = os.getenv("MEMO_MCP_PORT", "8010")
    server_url = f"http://{host}:{port}/mcp"

    print(f"Connecting to MCP server: {server_url}\n")

    connection = cast(
        StreamableHttpConnection,
        {
            "transport": "streamable_http",
            "url": server_url,
        },
    )
    client = MultiServerMCPClient({server_name: connection})
    tools = await client.get_tools(server_name=server_name)

    print(f"Found {len(tools)} tools:\n")

    for tool in tools:
        print(f"Tool: {tool.name}")
        print(f"Description: {tool.description}")
        print(f"Args Schema:")
        print(json.dumps(tool.args, indent=2))

        # LangChain tool로 변환된 schema 확인
        if hasattr(tool, 'args_schema'):
            print(f"\nLangChain Args Schema (model_json_schema):")
            try:
                schema = tool.args_schema.model_json_schema() if tool.args_schema else None
                print(json.dumps(schema, indent=2))
            except Exception as e:
                print(f"Error: {e}")

        print("-" * 80)
        print()


if __name__ == "__main__":
    asyncio.run(main())
