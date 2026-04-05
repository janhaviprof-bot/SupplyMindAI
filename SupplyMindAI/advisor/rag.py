"""
Lightweight RAG: SQL-backed snippets + markdown doc chunks, keyword retrieval.
"""
from __future__ import annotations

import re
import os
from pathlib import Path

from supplymind_db.supabase_client import execute_query


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", text)}


def _score_chunk(query: str, chunk: str) -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    c = _tokenize(chunk)
    if not c:
        return 0.0
    return len(q & c) / (len(q) ** 0.5 + 1e-6)


def load_doc_chunks() -> list[str]:
    root = _repo_root()
    paths = []
    for p in (root / "docs", root / "SupplyMindAI" / "docs"):
        if p.is_dir():
            paths.extend(sorted(p.glob("*.md")))
    chunks: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parts = re.split(r"\n(?=#{1,3}\s)", text)
        for part in parts:
            part = part.strip()
            if len(part) < 80:
                continue
            chunks.append(f"[{path.name}]\n{part[:4000]}")
    return chunks[:200]


def sql_summary_snippets() -> list[str]:
    out: list[str] = []
    try:
        rows = execute_query(
            """
            SELECT flag_status, COUNT(*)::int AS n
            FROM insights
            GROUP BY flag_status
            ORDER BY n DESC
            """,
            fetch=True,
        )
        if rows:
            parts = [f"{r['flag_status'] or 'unknown'}: {r['n']}" for r in rows]
            out.append("Insight flags: " + "; ".join(parts))
    except Exception as e:
        out.append(f"(insights summary unavailable: {e})")

    try:
        rows = execute_query(
            """
            SELECT hub_name, category, COUNT(*)::int AS n
            FROM risks
            GROUP BY hub_name, category
            ORDER BY n DESC
            LIMIT 15
            """,
            fetch=True,
        )
        if rows:
            lines = [f"{r['hub_name']} / {r['category']}: {r['n']}" for r in rows]
            out.append("Top hub–risk pairs:\n" + "\n".join(lines))
    except Exception as e:
        out.append(f"(risk pairs unavailable: {e})")

    try:
        rows = execute_query(
            """
            SELECT h.hub_name, h.status, h.current_load, h.max_capacity
            FROM hubs h
            ORDER BY h.hub_name
            LIMIT 40
            """,
            fetch=True,
        )
        if rows:
            lines = [
                f"{r['hub_name']}: status={r.get('status')}, load={r.get('current_load')}/{r.get('max_capacity')}"
                for r in rows
            ]
            out.append("Hub status snapshot:\n" + "\n".join(lines))
    except Exception as e:
        out.append(f"(hubs snapshot unavailable: {e})")

    return out


def retrieve(query: str, k: int = 6) -> list[str]:
    mode = (os.environ.get("RAG_RETRIEVAL_MODE") or "keyword").strip().lower()
    if mode == "embed":
        return _retrieve_embed(query, k)
    if mode == "hybrid":
        return _retrieve_hybrid(query, k)
    return _retrieve_keyword(query, k)


def _retrieve_keyword(query: str, k: int = 6) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for ch in sql_summary_snippets():
        candidates.append((_score_chunk(query, ch) + 0.5, ch))
    for ch in load_doc_chunks():
        candidates.append((_score_chunk(query, ch), ch))
    candidates.sort(key=lambda x: -x[0])
    seen = set()
    out: list[str] = []
    for score, ch in candidates:
        if score <= 0 and len(out) >= k // 2:
            continue
        key = ch[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(ch)
        if len(out) >= k:
            break
    return out if out else sql_summary_snippets()[:3]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (na * nb)


def _embed_one(client, text: str) -> list[float]:
    t = (text or "")[:8000]
    r = client.embeddings.create(model="text-embedding-3-small", input=t)
    return list(r.data[0].embedding)


def _retrieve_embed(query: str, k: int = 6) -> list[str]:
    from openai import OpenAI

    sql_chunks = sql_summary_snippets()
    doc_chunks = load_doc_chunks()
    all_c = sql_chunks + doc_chunks
    if not all_c:
        return []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _retrieve_keyword(query, k)
    client = OpenAI(api_key=api_key)
    try:
        qv = _embed_one(client, query)
        scored: list[tuple[float, str]] = []
        for ch in all_c:
            try:
                ev = _embed_one(client, ch[:8000])
                scored.append((_cosine(qv, ev), ch))
            except Exception:
                scored.append((_score_chunk(query, ch), ch))
        scored.sort(key=lambda x: -x[0])
        seen = set()
        out: list[str] = []
        for _, ch in scored:
            key = ch[:120]
            if key in seen:
                continue
            seen.add(key)
            out.append(ch)
            if len(out) >= k:
                break
        return out if out else sql_summary_snippets()[:3]
    except Exception:
        return _retrieve_keyword(query, k)


def _retrieve_hybrid(query: str, k: int = 6) -> list[str]:
    ke = _retrieve_embed(query, k)
    kk = _retrieve_keyword(query, k)
    seen = set()
    out: list[str] = []
    for ch in ke + kk:
        key = ch[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(ch)
        if len(out) >= k:
            break
    return out if out else sql_summary_snippets()[:3]