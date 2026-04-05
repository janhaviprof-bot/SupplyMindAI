"""
Shared LLM helpers for advisor agents (course-style agent_run chaining).
"""
from __future__ import annotations

import json
from typing import Any, Literal, Union, overload

ResponseType = Literal["text", "json"]


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text.strip()


@overload
def agent_run(
    client: Any,
    system: str,
    user: str,
    *,
    temperature: float = ...,
    model: str = ...,
    response_type: Literal["text"] = "text",
) -> str: ...


@overload
def agent_run(
    client: Any,
    system: str,
    user: str,
    *,
    temperature: float = ...,
    model: str = ...,
    response_type: Literal["json"],
) -> dict[str, Any]: ...


def agent_run(
    client,
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    model: str = "gpt-4o-mini",
    response_type: ResponseType = "text",
) -> Union[str, dict[str, Any]]:
    """
    Run a single chat completion (system + user). Use response_type='json' to parse JSON output.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    text = response.choices[0].message.content or ("{}" if response_type == "json" else "")
    if response_type == "json":
        text = _strip_json_fence(text)
        return json.loads(text)
    return text.strip()


def agent_completion_with_tools(
    client,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    temperature: float = 0.1,
    model: str = "gpt-4o-mini",
    tool_choice: str | dict[str, Any] = "auto",
):
    """
    One OpenAI chat completion turn with tool definitions (planner loop). Returns the full completion object.
    """
    return client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )
