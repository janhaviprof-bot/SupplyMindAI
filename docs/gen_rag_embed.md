~~~~python
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "SupplyMindAI"
P = ROOT / "advisor" / "rag.py"


def main():
    lines = P.read_text(encoding="utf-8").splitlines()
    if any("_retrieve_embed" in ln for ln in lines):
        print("rag skip")
        return
    # insert import os after import re
    out = []
    for i, ln in enumerate(lines):
        out.append(ln)
        if ln.strip() == "import re" and i + 1 < len(lines) and "import os" not in lines[i + 1]:
            out.append("import os")
    lines = out
    text = "\n".join(lines)
    old = '''def retrieve(query: str, k: int = 6) -> list[str]:
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
    return out if out else sql_summary_snippets()[:3]'''

    new = '''def retrieve(query: str, k: int = 6) -> list[str]:
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
    return out if out else sql_summary_snippets()[:3]'''

    if old not in text:
        raise SystemExit("retrieve block not found")
    P.write_text(text.replace(old, new), encoding="utf-8")
    print("rag ok")


if __name__ == "__main__":
    main()
~~~~
