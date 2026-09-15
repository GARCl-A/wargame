"""PostToolUse hook: run ruff on the .py file an Edit/Write just touched.

Catches broken imports, undefined names, and syntax errors the instant a file
is edited, instead of waiting for pytest or the pre-commit review to notice.

Shared by two different hook runners with two different stdin shapes:
- Claude Code: {"tool_input": {"file_path": ...}, ...}
- Antigravity: {"toolCall": {"args": {"TargetFile"/"AbsolutePath": ...}}, ...}
Output also differs: Claude Code reads a {"decision": "block", "reason": ...}
JSON object and feeds "reason" back to the model. Antigravity's PostToolUse
does not support that (its docs say the hook's stdout is ignored) — findings
are just printed as plain text so they show up wherever Antigravity logs hook
output; they do not reach the agent's context there. Unverified against a
live Antigravity run — test before relying on it.
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
    if path := (payload.get("tool_response") or {}).get("filePath"):
        return path
    tool_call_args = (payload.get("toolCall") or {}).get("args") or {}
    return tool_call_args.get("TargetFile") or tool_call_args.get("AbsolutePath")


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
    payload = json.load(sys.stdin)
    is_claude_code = "tool_input" in payload
    file_path = touched_file(payload)
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
    message = f"ruff encontrou problema(s) em {file_path}:\n{findings}"
    if is_claude_code:
        print(json.dumps({"decision": "block", "reason": message}))
    else:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    main()
