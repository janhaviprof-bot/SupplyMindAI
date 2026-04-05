# deployme.py — deploy the SupplyMind MCP FastAPI app to Posit Connect (rsconnect-python).
#
# Prerequisites:
#   pip install rsconnect-python python-dotenv
#
# requirements.txt in the inner SupplyMindAI folder (parent of mcp_server/) is used for the bundle.

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
