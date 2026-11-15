"""Single entry point for LLM access. Provider is chosen by LLM_PROVIDER (default: fake)."""
import json
import os
import re
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


_model_cache: dict[str, str] = {}
_SKIP = ("image", "tts", "live", "audio", "embedding", "robotics", "computer", "vision", "exp", "thinking", "preview", "customtools")


def _gemini_request(url: str, key: str, body: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def _pick_gemini_model(key: str) -> str:
    """Ask the API which models this key can use and take a recent flash model (names change over time)."""
    data = _gemini_request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", key)
    names = [m["name"].removeprefix("models/") for m in data.get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", []) and m["name"].startswith("models/gemini")]
    flash = [n for n in names if "flash" in n and not any(x in n for x in _SKIP)]
    pool = flash or [n for n in names if not any(x in n for x in _SKIP)] or names
    if not pool:
        raise LLMError("사용할 수 있는 Gemini 모델을 찾지 못했습니다")

    def rank(n: str):
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        return ("lite" in n, float(m[1]) if m else 0.0, n)  # fast flash-lite first (newest), then flash

    return max(pool, key=rank)


def complete(system: str, prompt: str, json_mode: bool = True) -> str:
    """Gemini generateContent over REST, or the local Claude Code CLI. Keys and models come from the environment only."""
    if provider() == "claude":
        return _claude_cli(system, prompt)
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, **({"responseMimeType": "application/json"} if json_mode else {})},
    }
    model = _model_cache.get(key) or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    # answers should be fast: turn the model's hidden "thinking" off; models that reject the setting get the plain request
    variants = [{**body, "generationConfig": {**body["generationConfig"], "thinkingConfig": {"thinkingBudget": 0}}}, body]
    try:
        i = 0
        switched = False
        while True:
            try:
                data = _gemini_request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", key, variants[i])
                break
            except urllib.error.HTTPError as e:
                if e.code == 404 and not switched:  # unknown model name: switch to one the key can really use
                    model = _model_cache[key] = _pick_gemini_model(key)
                    switched = True
                    continue
                if e.code == 400 and i == 0:  # this model does not accept thinkingConfig
                    i = 1
                    continue
                raise
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        raise LLMError(f"Gemini HTTP {e.code} (model {model})") from e
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as e:
        raise LLMError(f"Gemini call failed: {type(e).__name__} (model {model})") from e


def complete_json(system: str, prompt: str):
    text = complete(system, prompt, json_mode=True).strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return json.loads(text)
    except ValueError as e:
        raise LLMError("model returned invalid JSON") from e
