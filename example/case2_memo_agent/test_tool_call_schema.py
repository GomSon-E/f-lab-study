"""LLM에게 실제로 전달되는 tool schema 확인"""
import asyncio
import os
import json
from typing import cast

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StreamableHttpConnection
from langchain_openai import ChatOpenAI

load_dotenv()


def _fix_mcp_tool_schema(tool):
    """FastMCP의 nested 'request' schema를 LangChain이 이해할 수 있도록 수정."""
    if not hasattr(tool, 'args_schema') or not isinstance(tool.args_schema, dict):
        return tool

    schema = tool.args_schema

    # schema에 $defs가 있고, properties에 request.$ref가 있는 경우
    if '$defs' in schema and 'properties' in schema:
        props = schema['properties']
        if 'request' in props and '$ref' in props['request']:
            # $ref를 resolve
            ref_path = props['request']['$ref']
            if ref_path.startswith('#/$defs/'):
                def_name = ref_path.split('/')[-1]
                if def_name in schema['$defs']:
                    # request를 실제 정의로 대체
                    schema['properties']['request'] = schema['$defs'][def_name]
                    # required에 request가 있으면 유지
                    if 'required' not in schema:
                        schema['required'] = ['request']

    tool.args_schema = schema
    return tool


async def main():
    server_name = os.getenv("MEMO_MCP_SERVER_NAME", "memo")
    host = os.getenv("MEMO_MCP_HOST", "127.0.0.1")
    port = os.getenv("MEMO_MCP_PORT", "8010")
    server_url = f"http://{host}:{port}/mcp"

    connection = cast(
        StreamableHttpConnection,
        {
            "transport": "streamable_http",
            "url": server_url,
        },
    )
    client = MultiServerMCPClient({server_name: connection})
    tools = await client.get_tools(server_name=server_name)

    # Apply fix
    tools = [_fix_mcp_tool_schema(tool) for tool in tools]

    # bind_tools로 LLM에 전달
    llm = ChatOpenAI(model="gpt-4o-mini")
    llm_with_tools = llm.bind_tools(tools)

    # 실제 OpenAI에 전달되는 tools 확인
    print("=== LLM에 바인딩된 Tools ===\n")

    # LangChain의 bind_tools는 tools를 OpenAI format으로 변환
    # 실제로 전달되는 것을 확인하기 위해 get_format_instructions 확인
    for tool in tools:
        if tool.name == "create_memo":
            print(f"Tool name: {tool.name}")
            print(f"\nargs_schema type: {type(tool.args_schema)}")

            if isinstance(tool.args_schema, dict):
                print("\nargs_schema (dict):")
                print(json.dumps(tool.args_schema, indent=2))

            # tool_call_schema 확인
            if hasattr(tool, 'tool_call_schema'):
                print(f"\ntool_call_schema type: {type(tool.tool_call_schema)}")
                try:
                    schema = tool.tool_call_schema.model_json_schema()
                    print("\ntool_call_schema.model_json_schema():")
                    print(json.dumps(schema, indent=2))
                except Exception as e:
                    print(f"Error getting tool_call_schema: {e}")

            # get_input_schema 확인
            if hasattr(tool, 'get_input_schema'):
                try:
                    input_schema = tool.get_input_schema()
                    print(f"\nget_input_schema type: {type(input_schema)}")
                    if hasattr(input_schema, 'model_json_schema'):
                        schema = input_schema.model_json_schema()
                        print("\nget_input_schema().model_json_schema():")
                        print(json.dumps(schema, indent=2))
                except Exception as e:
                    print(f"Error getting input_schema: {e}")


if __name__ == "__main__":
    asyncio.run(main())
