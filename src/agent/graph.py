"""LangGraph ReAct agent construction, backed by Claude via langchain-anthropic."""
from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from src.agent.tools import ALL_TOOLS


@lru_cache(maxsize=8)
def build_agent(model: str, system_prompt: str, max_tokens: int = 4096):
    """Build (and cache) a LangGraph agent for a given model + system prompt pair."""
    llm = ChatAnthropic(model=model, max_tokens=max_tokens)
    return create_react_agent(llm, ALL_TOOLS, prompt=system_prompt)
