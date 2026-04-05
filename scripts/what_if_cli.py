#!/usr/bin/env python3
"""
Run the What-If advisor from the terminal.

Default output is homework/screenshot layout (three sections only). Use --full for debug.

Usage (from repository root):
  py scripts/what_if_cli.py "What if we cut capacity at our busiest hub by 20%?"
  py scripts/what_if_cli.py -q "Give me an operational snapshot" --date-range week
  py scripts/what_if_cli.py --full "..."              # verbose: metrics, JSON trace, extra headers
  py scripts/what_if_cli.py -i                        # interactive (same default layout per question)
  py scripts/what_if_cli.py --markdown-only "..."

Requires: SupplyMindAI/requirements.txt, .env with OPENAI_API_KEY and DB URL.
If tools use MCP, start the MCP server first (same as the Shiny app).

Exit codes (batch mode):
  0 — Completed (check r["error"] in full mode; homework mode may still exit 0 with stderr note)
  1 — Empty question, import failure, advisor exception, or error with no narrative
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
INNER = ROOT / "SupplyMindAI"
if str(INNER) not in sys.path:
    sys.path.insert(0, str(INNER))

_CHUNK_PREVIEW = 2000
_TOOL_PREVIEW = 8000
_TOOL_SNIPPET_CHARS = 100
_SEP = "=" * 72

# Must match names handled in advisor.tool_defs.run_supply_tool_local (only these can be MCP-called).
_REGISTERED_MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "list_hub_names",
        "get_in_transit_aggregate",
        "get_delivered_cohort_summary",
        "run_capacity_stress_pipeline",
        "run_optimization_simulation",
        "submit_planner_decision",
    }
)

_orig_tool_dispatch_call: Optional[Callable[..., Any]] = None


def _truncate(s: str, max_len: int = _CHUNK_PREVIEW) -> str:
    s = s or ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _agent_step_label(agent_name: str) -> str:
    n = (agent_name or "unknown").strip()
    s = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", n).lower()
    return f"agent_{s}"


def _rag_source_label(chunk: str, index: int) -> str:
    ch = chunk or ""
    head = ch.strip()[:500].lower()
    first_line = (ch.strip().split("\n", 1)[0] if ch.strip() else "").strip()

    if first_line.startswith("[") and "]" in first_line:
        fname = first_line[1 : first_line.index("]")]
        stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(fname).stem).strip("_").lower() or "doc"
        return f"rag_doc_{stem}"

    if "hub status snapshot" in head:
        return "rag_sql_hub_snapshot"
    if "insight flags" in head:
        return "rag_sql_insight_flags"
    if "top hub" in head and "risk" in head:
        return "rag_sql_hub_risk_pairs"

    return f"rag_snippet_{index}"


def _install_tool_audit(audit: list[dict[str, Any]]) -> None:
    global _orig_tool_dispatch_call
    import advisor.tool_dispatch as m

    if _orig_tool_dispatch_call is None:
        _orig_tool_dispatch_call = m.ToolDispatch.call

    def audited_call(
        self: Any,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        assert _orig_tool_dispatch_call is not None
        args = dict(arguments or {})
        try:
            out = _orig_tool_dispatch_call(self, name, arguments)
            audit.append(
                {
                    "tool": name,
                    "arguments": args,
                    "ok": True,
                    "result": out,
                }
            )
            return out
        except Exception as e:
            audit.append(
                {
                    "tool": name,
                    "arguments": args,
                    "ok": False,
                    "error": str(e),
                }
            )
            raise

    m.ToolDispatch.call = audited_call  # type: ignore[method-assign]


def _restore_tool_dispatch() -> None:
    global _orig_tool_dispatch_call
    if _orig_tool_dispatch_call is not None:
        import advisor.tool_dispatch as m

        m.ToolDispatch.call = _orig_tool_dispatch_call  # type: ignore[method-assign]
        _orig_tool_dispatch_call = None


def _tools_used_this_query(audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only rows for tools that were actually invoked (audit) and are registered MCP tools."""
    out: list[dict[str, Any]] = []
    for r in audit:
        name = r.get("tool")
        if isinstance(name, str) and name in _REGISTERED_MCP_TOOL_NAMES:
            out.append(r)
    return out


def _homework_tools_for_display(audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    For screenshots: show MCP tools that fetched/ran supply data for this query.
    Hide submit_planner_decision when real data tools were also called (planner step
    stays in section 1 agent_trace). If the only calls were planner submit, show those.
    """
    rows = _tools_used_this_query(audit)
    meta = frozenset({"submit_planner_decision"})
    data = [r for r in rows if r.get("tool") not in meta]
    return data if data else rows


def _dedupe_tool_rows_last_wins(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per tool name; keep the last call (e.g. final hub/stress args). Order = first-seen names."""
    by_name: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for r in rows:
        n = r.get("tool")
        if not isinstance(n, str):
            continue
        if n not in order:
            order.append(n)
        by_name[n] = r
    return [by_name[n] for n in order]


def _tool_payload_preview(row: dict[str, Any], max_len: int) -> str:
    """Single-line JSON-ish summary of args + result/error for this tool call."""
    if row.get("ok"):
        payload: Any = {"arguments": row.get("arguments"), "result": row.get("result")}
    else:
        payload = {"arguments": row.get("arguments"), "error": row.get("error")}
    raw = json.dumps(payload, default=str, ensure_ascii=False)
    one_line = " ".join(raw.split())
    return _truncate(one_line, max_len)


def _print_tool_audit(
    rows: list[dict[str, Any]],
    *,
    homework_header: Optional[str] = None,
    max_payload_chars: int = _TOOL_SNIPPET_CHARS,
    dedupe_by_tool_name: bool = False,
) -> None:
    if dedupe_by_tool_name:
        rows = _dedupe_tool_rows_last_wins(rows)
    if homework_header:
        print(_SEP)
        print(homework_header)
        print(_SEP)
    else:
        print(_SEP)
        print("tools_called (MCP function calling: tool_<name>, arguments, result)")
        print(_SEP)
    if not rows:
        print("(no MCP tools were invoked for this query.)")
        return
    counts: dict[str, int] = {}
    for row in rows:
        name = str(row["tool"])
        counts[name] = counts.get(name, 0) + 1
        n = counts[name]
        suffix = f"__{n}" if n > 1 else ""
        print(f"\n--- tool_{name}{suffix} ---")
        print(_tool_payload_preview(row, max_payload_chars))


def _print_rag(q: str) -> None:
    from advisor.rag import retrieve

    print(_SEP)
    print("RAG_retrieval - context snippets passed to the advisor (not agent steps)")
    print("(labels: rag_doc_* = markdown doc, rag_sql_* = live DB summary, rag_snippet_* = other)")
    print(_SEP)
    try:
        chunks = retrieve(q, k=6)
    except Exception as e:
        print(f"(retrieve failed: {e})")
        chunks = []
    if not chunks:
        print("(no chunks)")
    else:
        for i, ch in enumerate(chunks, 1):
            label = _rag_source_label(ch, i)
            print(f"\n--- {label} ---\n{_truncate(ch)}\n")


def _retrieve_chunks(q: str) -> list[str]:
    from advisor.rag import retrieve

    try:
        return retrieve(q, k=6)
    except Exception:
        return []


def _print_homework_output(
    *,
    trace: list[dict[str, Any]],
    chunks: list[str],
    narrative: str,
    tool_audit: list[dict[str, Any]],
    err: Optional[str],
) -> None:
    # 1) Multi-agent workflow
    print(_SEP)
    print("1) Multi-agent workflow in action")
    print(_SEP)
    if not trace:
        print("(empty agent_trace)")
    else:
        for step in trace:
            raw = step.get("agent") or "unknown"
            label = _agent_step_label(str(raw))
            summary = (step.get("summary") or "").strip()
            print(f"\n--- {label} ---")
            print(_truncate(summary, 4000))

    # 2) RAG retrieval and response
    print(f"\n{_SEP}")
    print("2) RAG retrieval and response")
    print(_SEP)
    print("--- retrieval (top-k context snippets) ---")
    if not chunks:
        print("(no chunks)")
    else:
        for i, ch in enumerate(chunks, 1):
            label = _rag_source_label(ch, i)
            print(f"\n--- {label} ---\n{_truncate(ch)}\n")
    print("\n--- response (natural-language answer) ---")
    if err:
        print(f"(advisor error: {err})")
    print((narrative or "").strip() or "(empty)")

    # 3) Tools — only calls made during this advisor run (snapshot below)
    used = _homework_tools_for_display(tool_audit)
    _print_tool_audit(
        used,
        homework_header="3) Function calling / tool usage",
        max_payload_chars=_TOOL_SNIPPET_CHARS,
        dedupe_by_tool_name=True,
    )


def _process_one(
    q: str,
    *,
    date_range: str,
    show_rag: bool,
    show_tools: bool,
    show_trace: bool,
    show_answer: bool,
    markdown_only: bool,
    tool_audit: list[dict[str, Any]],
    homework: bool,
) -> int:
    from advisor.what_if import run_what_if_advisor

    tool_audit.clear()

    if homework and not markdown_only:
        chunks = _retrieve_chunks(q)
        try:
            r = run_what_if_advisor(q, date_range=date_range)
        except Exception as e:
            print(f"{type(e).__name__}: {e}", file=sys.stderr)
            err_txt = str(e)
            if "POSTGRES_CONNECTION_STRING" in err_txt or "DIRECT_URL" in err_txt or "DATABASE_URL" in err_txt:
                print(
                    "Hint: Tools run on the MCP server (SUPPLYMIND_MCP_URL). That host needs "
                    "POSTGRES_* / DIRECT_URL / DATABASE_URL too.",
                    file=sys.stderr,
                )
            else:
                print(
                    "Hint: Start MCP or set SUPPLYMIND_MCP_URL.",
                    file=sys.stderr,
                )
            return 1

        used_tools = list(tool_audit)
        _print_homework_output(
            trace=r.get("agent_trace") or [],
            chunks=chunks,
            narrative=str(r.get("narrative_markdown") or ""),
            tool_audit=used_tools,
            err=r.get("error"),
        )
        err = r.get("error")
        if err and not (r.get("narrative_markdown") or "").strip():
            return 1
        return 0

    # --- full / verbose layout ---
    if show_rag and not markdown_only:
        _print_rag(q)

    try:
        r = run_what_if_advisor(q, date_range=date_range)
    except Exception as e:
        print(_SEP)
        print("advisor_failed")
        print(_SEP)
        print(f"{type(e).__name__}: {e}")
        err_txt = str(e)
        if "POSTGRES_CONNECTION_STRING" in err_txt or "DIRECT_URL" in err_txt or "DATABASE_URL" in err_txt:
            print(
                "\nHint: Your laptop .env can be fine (RAG/sql works here) but advisor *tools* run on the "
                "**MCP server** at SUPPLYMIND_MCP_URL. That host must also have POSTGRES_CONNECTION_STRING "
                "(or DIRECT_URL / DATABASE_URL) in *its* environment. Or point SUPPLYMIND_MCP_URL to local "
                "uvicorn and run MCP on this machine where .env lives.",
                file=sys.stderr,
            )
        else:
            print(
                "\nHint: tools call MCP by default. Start the server (e.g. uvicorn) or set "
                "SUPPLYMIND_MCP_URL if it runs elsewhere.",
                file=sys.stderr,
            )
        return 1

    if show_tools and not markdown_only:
        _print_tool_audit(
            _tools_used_this_query(tool_audit),
            max_payload_chars=_TOOL_PREVIEW,
            dedupe_by_tool_name=False,
        )

    if show_trace and not markdown_only:
        print(_SEP)
        print("agent_trace - LLM steps (labels: agent_<step>)")
        print(_SEP)
        trace = r.get("agent_trace") or []
        if not trace:
            print("(empty trace)")
        else:
            for step in trace:
                raw = step.get("agent") or "unknown"
                label = _agent_step_label(str(raw))
                summary = (step.get("summary") or "").strip()
                print(f"\n--- {label} ---")
                print(_truncate(summary, 4000))
            print(f"\n{_SEP}\nagent_trace_json (machine-readable)\n{_SEP}")
            print(json.dumps(trace, indent=2, ensure_ascii=False))

    err = r.get("error")
    if err and not markdown_only:
        print(_SEP)
        print("error")
        print(_SEP)
        print(err)
    elif err and markdown_only:
        print(err, file=sys.stderr)

    lines = r.get("metrics_lines") or []
    if lines and not markdown_only:
        print(_SEP)
        print("metrics_lines")
        print(_SEP)
        for line in lines:
            print(line)

    if show_answer:
        print(_SEP)
        print("response_narration - final natural-language answer (markdown)")
        print(_SEP)
        print((r.get("narrative_markdown") or "").strip() or "(empty)")

    if err and not (r.get("narrative_markdown") or "").strip():
        return 1
    return 0


def _interactive_loop(args: argparse.Namespace, tool_audit: list[dict[str, Any]]) -> int:
    dr = args.date_range
    homework = args.homework
    print(_SEP)
    print("What-If CLI — interactive mode")
    if homework:
        print("Output: (1) multi-agent workflow (2) RAG + response (3) tools — use --full for verbose.")
    else:
        print(f"Verbose mode. Baseline date_range: {dr}")
    print("Type a question at user: — empty line, quit, or exit to stop.")
    print(_SEP)
    last_code = 0
    while True:
        try:
            line = input("user: ")
        except EOFError:
            print("\n(exit)")
            break
        q = (line or "").strip()
        if not q or q.lower() in ("quit", "exit"):
            break
        if q.lower() == "help":
            print(
                "Homework layout (default): sections 1–3 only. Flags: --full for all debug output.\n"
            )
            continue

        print()
        last_code = _process_one(
            q,
            date_range=dr,
            show_rag=args.show_rag,
            show_tools=args.show_tools,
            show_trace=args.show_trace,
            show_answer=args.show_answer,
            markdown_only=args.markdown_only,
            tool_audit=tool_audit,
            homework=homework,
        )
        print("\n")
    return last_code


def main() -> int:
    p = argparse.ArgumentParser(description="What-If advisor CLI")
    p.add_argument(
        "question_parts",
        nargs="*",
        help="Question text (batch mode). Ignored if -q is set.",
    )
    p.add_argument(
        "-q",
        "--question",
        default="",
        help="Full question string (batch mode).",
    )
    p.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Prompt repeatedly with user: until quit/exit.",
    )
    p.add_argument(
        "--date-range",
        default="week",
        choices=["yesterday", "week", "month", "year"],
        help="Baseline window for cohort/optimization tools (default: week).",
    )
    p.add_argument(
        "--full",
        action="store_true",
        help="Verbose output: metrics, raw JSON agent_trace, extra RAG headers, old section order.",
    )
    p.add_argument("--show-rag", dest="show_rag", action="store_true", default=True)
    p.add_argument("--no-rag", dest="show_rag", action="store_false")
    p.add_argument("--show-tools", dest="show_tools", action="store_true", default=True)
    p.add_argument("--no-tools", dest="show_tools", action="store_false")
    p.add_argument("--show-trace", dest="show_trace", action="store_true", default=True)
    p.add_argument("--no-trace", dest="show_trace", action="store_false")
    p.add_argument("--show-answer", dest="show_answer", action="store_true", default=True)
    p.add_argument("--no-answer", dest="show_answer", action="store_false")
    p.add_argument(
        "--markdown-only",
        action="store_true",
        help="Print only narrative_markdown (no RAG, tools, or trace).",
    )
    args = p.parse_args()

    args.homework = not args.full

    if args.markdown_only:
        args.show_rag = False
        args.show_tools = False
        args.show_trace = False
        args.show_answer = True
        args.homework = False

    try:
        import advisor.tool_dispatch  # noqa: F401
        import advisor.what_if  # noqa: F401
    except ImportError as e:
        print(f"Error: could not import advisor modules: {e}", file=sys.stderr)
        return 1

    tool_audit: list[dict[str, Any]] = []
    _install_tool_audit(tool_audit)
    try:
        if args.interactive:
            return _interactive_loop(args, tool_audit)

        q = (args.question or "").strip()
        if not q:
            q = " ".join(args.question_parts).strip()
        if not q:
            print("Error: provide a question, or use -i for interactive mode.", file=sys.stderr)
            return 1

        return _process_one(
            q,
            date_range=args.date_range,
            show_rag=args.show_rag,
            show_tools=args.show_tools,
            show_trace=args.show_trace,
            show_answer=args.show_answer,
            markdown_only=args.markdown_only,
            tool_audit=tool_audit,
            homework=args.homework,
        )
    finally:
        _restore_tool_dispatch()


if __name__ == "__main__":
    raise SystemExit(main())
