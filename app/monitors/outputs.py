"""Detección de monitores (salidas de pantalla) mediante kscreen-doctor."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess

log = logging.getLogger("wel.monitors")


def list_outputs() -> list[dict]:
    """Devuelve las salidas conectadas: [{"name": "DP-2", "size": "2560x1440", ...}]"""
    outputs: list[dict] = []
    if shutil.which("kscreen-doctor") is None:
        return outputs
    try:
        result = subprocess.run(
            ["kscreen-doctor", "-o"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return outputs

    current: dict | None = None
    for raw_line in result.stdout.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", raw_line)
        stripped = line.strip()
        if stripped.startswith("Output:"):
            if current:
                outputs.append(current)
            # "Output: 1 DP-2 uuid" → el nombre es el segundo token
            parts = stripped.split()
            current = {"index": len(outputs), "name": parts[2] if len(parts) > 2 else parts[1],
                       "size": "", "enabled": False}
            continue
        if current is None:
            continue
        if stripped.startswith("enabled"):
            current["enabled"] = True
        m = re.match(r"Modes:.*?(\d+x\d+)", stripped)
        if m and not current["size"]:
            current["size"] = m.group(1)
        m = re.search(r"\*?(\d+x\d+)@[\d.]+[!*]", stripped)
        if m:
            current["size"] = m.group(1)
    if current:
        outputs.append(current)

    log.info("salidas detectadas: %s", outputs)
    return outputs
