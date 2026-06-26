from providers.llm.base import LLMProvider
from core.llm_processor import LLMProcessor


class GroqLLMProvider(LLMProvider):
    def __init__(self, model_name: str = None):
        """
        Groq-backed LLM provider.

        Scene extraction is handled by the core LLMProcessor, which talks to
        whichever backend `providers.llm.chat_client.get_chat_client()` selects.
        With LLM_PROVIDER=groq that is the Groq cloud API, so no local Ollama is
        required (this is what makes the pipeline deployable in a container).
        """
        self.processor = LLMProcessor(model_name=model_name)

    def process_text(self, text: str, panel_count: int = None, layout_type: str = None) -> dict:
        return self.processor.process_text(text, panel_count=panel_count, layout_type=layout_type)
