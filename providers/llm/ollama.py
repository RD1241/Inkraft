from providers.llm.base import LLMProvider
from core.llm_processor import LLMProcessor

class OllamaLLMProvider(LLMProvider):
    def __init__(self, model_name: str = None):
        """
        Initializes the Ollama LLM provider.
        
        Args:
            model_name (str, optional): The name of the LLM model to use.
        """
        self.processor = LLMProcessor(model_name=model_name)

    def process_text(self, text: str, panel_count: int = None, layout_type: str = None) -> dict:
        """
        Delegates storyboard generation to the core LLMProcessor.
        """
        return self.processor.process_text(text, panel_count=panel_count, layout_type=layout_type)
