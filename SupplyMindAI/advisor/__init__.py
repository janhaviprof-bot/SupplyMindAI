"""What-If Advisor: multi-agent scenario analysis with RAG (chatbot UI in app).

Avoid importing heavy submodules here so ``import advisor.tool_defs`` does not pull in
``what_if`` (and thus ``db``) before ``mcp_server`` has finished package setup.
"""

from __future__ import annotations

__all__ = ["run_what_if_advisor"]


def __getattr__(name: str):
    if name == "run_what_if_advisor":
        from advisor.what_if import run_what_if_advisor

        return run_what_if_advisor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
