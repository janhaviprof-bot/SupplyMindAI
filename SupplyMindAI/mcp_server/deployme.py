# deployme.py — deploy the SupplyMind MCP FastAPI app to Posit Connect (rsconnect-python).
#
# Prerequisites:
#   pip install rsconnect-python python-dotenv
#
# requirements.txt in the inner SupplyMindAI folder (parent of mcp_server/) is used for the bundle.

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Inner SupplyMindAI (contains advisor/, analysis/, db/, requirements.txt); not mcp_server/ alone.
APP_DIR = Path(__file__).resolve().parent.parent
CONNECT_SERVER = os.environ.get("CONNECT_SERVER") or os.environ.get(
    "CONNECT_URL", "https://your-connect-server.com"
)
CONNECT_API_KEY = os.environ.get("CONNECT_API_KEY", "YOUR_KEY_HERE")
CONNECT_NAME = os.environ.get("CONNECT_NAME", "supplymind-mcp")
DEPLOY_TITLE = os.environ.get("CONNECT_DEPLOY_TITLE", "supplymind-mcp")
# Connect often has older Python than your laptop; rsconnect still records local interpreter in manifest.
CONNECT_PYTHON_VERSION = os.environ.get("CONNECT_PYTHON_VERSION", "3.12.4")
ENTRYPOINT = "mcp_server.server:app"

subprocess.run(
    [
        "rsconnect",
        "add",
        "--server",
        CONNECT_SERVER,
        "--api-key",
        CONNECT_API_KEY,
        "--name",
        CONNECT_NAME,
    ],
    check=True,
)

subprocess.run(
    [
        "rsconnect",
        "write-manifest",
        "fastapi",
        "--entrypoint",
        ENTRYPOINT,
        "--overwrite",
        str(APP_DIR),
    ],
    check=True,
)

manifest_path = APP_DIR / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest.setdefault("python", {})["version"] = CONNECT_PYTHON_VERSION
manifest.setdefault("environment", {}).setdefault("python", {})[
    "requires"
] = f"=={CONNECT_PYTHON_VERSION}"
manifest_path.write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)

subprocess.run(
    [
        "rsconnect",
        "deploy",
        "fastapi",
        "--name",
        CONNECT_NAME,
        "--title",
        DEPLOY_TITLE,
        "--entrypoint",
        ENTRYPOINT,
        str(APP_DIR),
    ],
    check=True,
)

# After deployment, set Connect Variables on the API: OPENAI_API_KEY, POSTGRES_CONNECTION_STRING (or DIRECT_URL).
# MCP URL pattern: https://<connect>/content/<id>/mcp — set SUPPLYMIND_MCP_URL on the Shiny content accordingly.
