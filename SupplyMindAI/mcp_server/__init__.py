"""MCP HTTP server package.

Posit Connect imports ``mcp_server.server`` via the package; this file runs first.
Ensure the bundle root (parent of ``mcp_server/``) is on ``sys.path`` so ``db`` resolves
before any submodule imports ``db.*`` (import order can differ from local uvicorn).
"""
from __future__ import annotations

import sys
from pathlib import Path

_bundle = Path(__file__).resolve().parent.parent
if str(_bundle) not in sys.path:
    sys.path.insert(0, str(_bundle))
