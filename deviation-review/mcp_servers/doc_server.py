#!/usr/bin/env python3
"""Read-only MCP server over governing documents (CLAUDE.md Phase 2: 4 read-only servers).

Extracts text from the two synthetic PDFs (data/SOP-Drying-001.pdf, data/Protocol-CT-2026-07.pdf)
via pypdf, splits each into numbered-section chunks, and indexes them with BM25 (rank_bm25) for
retrieval. BM25-only per the project's open item (hybrid retrieval deferred until an eval run
shows retrieval misses).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

SERVER = "documents"
DOC_FILES = ["SOP-Drying-001.pdf", "Protocol-CT-2026-07.pdf"]

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def extract_chunks(filename: str) -> list[dict]:
    """One chunk per numbered section ('1. Purpose. ...'), plus a leading title chunk."""
    path = os.path.join(common.DATA_DIR, filename)
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    parts = re.split(r"\n(?=\d+\.\s)", text.strip())
    chunks = []
    for i, part in enumerate(parts):
        cleaned = re.sub(r"\s+", " ", part).strip()
        if cleaned:
            chunks.append({"chunk_id": f"{filename}#{i}", "file": filename, "text": cleaned})
    return chunks


def build_index():
    chunks = [c for f in DOC_FILES for c in extract_chunks(f)]
    corpus = [tokenize(c["text"]) for c in chunks]
    return chunks, BM25Okapi(corpus)


CHUNKS, BM25 = build_index()

mcp = FastMCP(
    SERVER,
    instructions=(
        "Read-only BM25 search over the SOP and study-protocol PDFs (data/*.pdf). Every "
        "response carries a source block per CLAUDE.md Section 6, with the source chunk_id so "
        "a reviewer can trace a claim back to the exact document passage."
    ),
)


@mcp.tool()
def search_documents(query: str, top_k: int = 3) -> dict:
    """BM25 search over SOP/protocol chunks. Returns up to top_k chunks ranked by relevance,
    each with its bm25 score, so the caller can judge whether a match is actually usable
    evidence rather than a weak keyword collision."""
    scores = BM25.get_scores(tokenize(query))
    ranked = sorted(range(len(CHUNKS)), key=lambda i: scores[i], reverse=True)[:top_k]
    results = []
    for i in ranked:
        chunk = CHUNKS[i]
        value = {"text": chunk["text"], "score": round(float(scores[i]), 4)}
        results.append(
            common.with_source(value, SERVER, "search_documents", chunk["chunk_id"], chunk["file"])
        )
    return {"query": query, "results": results}


if __name__ == "__main__":
    mcp.run()
