"""Single entry point for LLM access. Provider is chosen by LLM_PROVIDER (default: fake)."""
import os


class LLMError(Exception):
    """Raised when the model call fails. Backend maps this to HTTP 502."""


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "fake").lower()


def complete(system: str, prompt: str) -> str:
    # ponytail: gemini wiring waits for the API key; check the official SDK docs before writing it.
    raise LLMError("gemini provider is not wired yet (set LLM_PROVIDER=fake)")
