"""Factory for a tool-enabled finance agent using LangChain tools."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine

try:
    from langchain.agents import create_agent
except ImportError:  # pragma: no cover
    create_agent = None

from langchain_openai import AzureChatOpenAI

from prompts.catalog import get_prompt
from tools.finance_tools import configure_finance_tools

SYSTEM_PROMPT = get_prompt("finance-tool-agent")["template"]


def create_finance_tool_agent(
    engine: Engine,
    *,
    endpoint: str,
    api_key: str,
    api_version: str,
    deployment: str,
) -> Any:
    if create_agent is None:
        raise RuntimeError("LangChain is required to enable tool-calling for the finance agent.")
    if not all((endpoint, api_key, api_version, deployment)):
        raise ValueError("Azure OpenAI settings are required to create the finance tool agent.")

    llm = AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        azure_deployment=deployment,
        temperature=0,
        max_retries=1,
    )
    tools = configure_finance_tools(engine)
    return create_agent(
        llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        debug=True,
    )
