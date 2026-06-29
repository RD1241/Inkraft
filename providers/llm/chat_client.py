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

# Fallback chain: if the primary model hits its per-day token limit (429), retry
# on these models IN ORDER before the pipeline degrades to the rule-based extractor
# (which ghosts capitalized words as characters). `llama-3.1-8b-instant` has a
# SEPARATE, much larger free-tier daily token bucket than the 70B model, so it keeps
# real LLM extraction alive when the 70B is exhausted. Quality is lower than 70B but
# far better than rule-based. Override / extend with the GROQ_FALLBACK_MODELS env var
# (comma-separated). Set it empty to disable the chain.
_GROQ_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get(
        "GROQ_FALLBACK_MODELS", "llama-3.1-8b-instant"
    ).split(",") if m.strip()
]


def _is_rate_limit(exc: Exception) -> bool:
    """True if the exception is a Groq per-day/per-minute token rate-limit (429)."""
    s = str(exc).lower()
    return "rate_limit" in s or "429" in s or "tokens per day" in s or "tpd" in s


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
        base_params = {"messages": messages or []}
        # Map the ollama options we actually use onto Groq params; ignore the
        # rest (num_ctx / keep_alive are Ollama-only concepts).
        if options.get("temperature") is not None:
            base_params["temperature"] = options["temperature"]
        if options.get("num_predict"):
            base_params["max_tokens"] = int(options["num_predict"])

        # Try the primary model, then the fallback chain on a rate-limit (429), so a
        # per-day token cap on the 70B model doesn't drop us to rule-based extraction.
        primary = self._resolve_model(model)
        chain = [primary] + [m for m in _GROQ_FALLBACK_MODELS if m != primary]
        last_exc = None
        for idx, mdl in enumerate(chain):
            try:
                resp = self._client.chat.completions.create(model=mdl, **base_params)
                content = resp.choices[0].message.content if resp.choices else ""
                if idx > 0:
                    print(f"[GroqChatClient] Primary '{primary}' unavailable; "
                          f"served by fallback model '{mdl}'.")
                # Mirror ollama.Client.chat()'s return shape used across the codebase.
                return {"message": {"content": content}}
            except Exception as exc:
                last_exc = exc
                is_rl = _is_rate_limit(exc)
                more = idx < len(chain) - 1
                if is_rl and more:
                    print(f"[GroqChatClient] '{mdl}' rate-limited (429); "
                          f"falling back to '{chain[idx + 1]}'.")
                    continue
                # Non-rate-limit error, or no fallbacks left → surface to the caller's
                # retry loop (which ultimately drops to rule-based extraction).
                raise
        # Defensive: loop always returns or raises, but satisfy the type checker.
        raise last_exc if last_exc else RuntimeError("Groq chat failed with no models")


def get_chat_client():
    """Return an ollama-compatible chat client for the configured LLM provider."""
    if using_groq():
        return GroqChatClient()
    import ollama
    return ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://127.0.0.1:11434"))
