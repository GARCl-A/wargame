"""PostToolUse hook: run ruff on the .py file an Edit/Write just touched.

Catches broken imports, undefined names, and syntax errors the instant a file
is edited, instead of waiting for pytest or the pre-commit review to notice.
Reads Claude Code's hook payload ({"tool_input": {"file_path": ...}}) and answers
with {"decision": "block", "reason": ...} so the findings reach the model.
"""
import json
import shutil
import site
import subprocess
import sys
from pathlib import Path


def touched_file(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    if path := tool_input.get("file_path"):
        return path
    return (payload.get("tool_response") or {}).get("filePath")


def find_ruff() -> str | None:
    if on_path := shutil.which("ruff"):
        return on_path
    exe_name = "ruff.exe" if sys.platform == "win32" else "ruff"
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    candidates = [
        Path(site.getuserbase()) / scripts_dir / exe_name,
        Path(__file__).resolve().parent.parent / ".venv" / scripts_dir / exe_name,
    ]
    return next((str(c) for c in candidates if c.exists()), None)


def main() -> None:
    file_path = touched_file(json.load(sys.stdin))
    if not file_path or not file_path.endswith(".py") or not Path(file_path).exists():
        return

    ruff = find_ruff()
    if ruff is None:
        return

    result = subprocess.run(
        [ruff, "check", "--select", "F,E9", "--quiet", file_path],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    findings = (result.stdout + result.stderr).strip()
    print(json.dumps({"decision": "block", "reason": f"ruff found problem(s) in {file_path}:\n{findings}"}))


if __name__ == "__main__":
    main()
