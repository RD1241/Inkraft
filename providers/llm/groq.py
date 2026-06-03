from providers.llm.base import LLMProvider

class GroqLLMProvider(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Initializes the Groq LLM provider stub.
        """
        self.api_key = api_key
        self.model_name = model_name or "llama3-70b-8192"

    def process_text(self, text: str) -> dict:
        """
        Groq stub implementation for extracting scenes.
        """
        print(f"[GroqLLMProvider] STUB: Generating storyboard for text with model {self.model_name}")
        # Return a simple mock or empty response since it's a stub
        return {"scenes": []}
