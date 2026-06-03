from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def process_text(self, text: str, panel_count: int = None, layout_type: str = None) -> dict:
        """
        Extract scenes and storyboard from novel text.
        
        Args:
            text (str): The novel input text.
            panel_count (int, optional): The target panel count.
            layout_type (str, optional): The layout type determining count/bias.
            
        Returns:
            dict: Storyboard JSON with 'global_environment' and 'scenes'.
        """
        pass
