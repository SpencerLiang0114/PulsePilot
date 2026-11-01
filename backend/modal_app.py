"""Deploy the existing inference container with `modal deploy backend/modal_app.py`."""
import os
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
app = modal.App("pulsepilot")
image = modal.Image.from_dockerfile(
    ROOT / "backend/Dockerfile", context_dir=ROOT,
)
runtime = modal.Secret.from_dict({
    key: os.environ[key]
    for key in ("MODEL_API_KEY", "META_MODEL", "AGENT_MODE", "ALLOWED_ORIGINS")
    if key in os.environ
})


@app.function(
    image=image,
    secrets=[runtime],
    cpu=4,
    memory=4096,
    max_containers=1,
    min_containers=0,
    scaledown_window=300,
    timeout=600,
    include_source=False,
    serialized=True,
)
@modal.concurrent(max_inputs=8)
@modal.web_server(8000, startup_timeout=60)
def inference():
    import subprocess

    subprocess.Popen([
        "/app/backend/.venv/bin/python", "-m", "uvicorn", "pulsepilot.app:app",
        "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000",
        "--workers", "1", "--ws-max-size", "1500008",
    ])
