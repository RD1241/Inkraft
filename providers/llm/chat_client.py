"""
providers/llm/chat_client.py

A thin chat-client factory so the LLM pipeline can run on either local Ollama
or the Groq cloud API *without changing call sites*. Both call sites
(`core/llm_processor.py` and `core/storyboard_director.py`) use:

    response = client.chat(model=..., messages=[...], options={...})
    content  = response["message"]["content"]

so `GroqChatClient` mirrors that exact shape. Selection is driven by the
`LLM_PROVIDER` env var (`groq` or `ollama`). This is what lets the app run in a
container with no local Ollama — set LLM_PROVIDER=groq + GROQ_API_KEY.
"""
import os
from config import settings

# Map legacy/ollama model names (e.g. "llama3") to a valid current Groq model id.
# Override with the GROQ_MODEL env var.
_GROQ_DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def _llm_provider() -> str:
    return (os.environ.get("LLM_PROVIDER")
            or getattr(settings, "LLM_PROVIDER", "")
            or "ollama").strip().lower()


def using_groq() -> bool:
    return _llm_provider() == "groq"


class GroqChatClient:
    """Exposes the subset of ollama.Client used in this codebase, backed by Groq."""

    def __init__(self, api_key: str = None, default_model: str = None):
        from groq import Groq
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
        self._client = Groq(api_key=self.api_key)
        self.default_model = default_model or _GROQ_DEFAULT_MODEL

    def _resolve_model(self, model) -> str:
        # Call sites pass settings.LLM_MODEL ("llama3"), which is not a Groq id.
        # Honor an explicitly groq-style id (has a hyphen + digit), else use default.
        m = str(model) if model else ""
        if "-" in m and any(ch.isdigit() for ch in m):
            return m
        return self.default_model

    def chat(self, model=None, messages=None, options=None, **kwargs) -> dict:
        options = options or {}
        params = {
            "model": self._resolve_model(model),
            "messages": messages or [],
        }
        # Map the ollama options we actually use onto Groq params; ignore the
        # rest (num_ctx / keep_alive are Ollama-only concepts).
        if options.get("temperature") is not None:
            params["temperature"] = options["temperature"]
        if options.get("num_predict"):
            params["max_tokens"] = int(options["num_predict"])
        resp = self._client.chat.completions.create(**params)
        content = resp.choices[0].message.content if resp.choices else ""
        # Mirror ollama.Client.chat()'s return shape used across the codebase.
        return {"message": {"content": content}}


def get_chat_client():
    """Return an ollama-compatible chat client for the configured LLM provider."""
    if using_groq():
        return GroqChatClient()
    import ollama
    return ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://127.0.0.1:11434"))
