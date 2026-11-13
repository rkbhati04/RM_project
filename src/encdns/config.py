"""Configuration and reproducibility metadata helpers."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

def load_project_config(path: Path | None = None) -> dict[str, Any]:
    import yaml

    path = path or ROOT / "config" / "project.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def command_version(command: str) -> str | None:
    try:
        completed = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return (completed.stdout or completed.stderr).strip().splitlines()[0] if completed.returncode == 0 else None

def run_metadata(config_path: Path, dataset_path: Path) -> dict[str, Any]:
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "config_sha256": sha256_file(config_path), "dataset_sha256": sha256_file(dataset_path), "python": platform.python_version(), "platform": platform.platform(), "q_version": command_version("q"), "tshark_version": command_version("tshark")}

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
