"""Single entry point for LLM access. Provider is chosen by LLM_PROVIDER (default: fake)."""
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request


class LLMError(Exception):
    """Raised when the model call fails. Backend maps this to HTTP 502."""


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "fake").lower()


def _claude_cli(system: str, prompt: str) -> str:
    """Use the locally logged-in Claude Code (your own Claude plan) as the model: `claude -p`.
    Runs in an empty temp dir with tools, hooks and project settings off so only the prompt matters."""
    exe = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    cmd = [exe, "-p", "--system-prompt", system, "--tools", "", "--no-session-persistence", "--setting-sources", "",
           "--model", os.environ.get("CLAUDE_MODEL", "sonnet"), "--output-format", "text"]
    try:
        with tempfile.TemporaryDirectory() as cwd:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LLMError(f"Claude Code 호출에 실패했습니다: {type(e).__name__}") from e
    if r.returncode != 0 or not r.stdout.strip():
        first = (r.stderr or r.stdout).strip().splitlines()[:1]
        raise LLMError("Claude Code 호출에 실패했습니다: " + (first[0][:120] if first else "빈 응답"))
    return r.stdout.strip()


def complete(system: str, prompt: str, json_mode: bool = True) -> str:
    """Gemini generateContent over REST, or the local Claude Code CLI. Keys and models come from the environment only."""
    if provider() == "claude":
        return _claude_cli(system, prompt)
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, **({"responseMimeType": "application/json"} if json_mode else {})},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        raise LLMError(f"Gemini HTTP {e.code}") from e
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as e:
        raise LLMError(f"Gemini call failed: {type(e).__name__}") from e


def complete_json(system: str, prompt: str):
    text = complete(system, prompt, json_mode=True).strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return json.loads(text)
    except ValueError as e:
        raise LLMError("model returned invalid JSON") from e
