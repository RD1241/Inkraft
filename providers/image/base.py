from abc import ABC, abstractmethod

class ImageProvider(ABC):
    @abstractmethod
    def create_base_latents(self, seed: int = 42):
        """
        Create base noise latents for consistent image layout (if supported).
        """
        pass

    @abstractmethod
    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str,
        output_path: str,
        seed: int = 42,
        reference_image_path: str = None,
        reference_strength: float = None,
        base_latents=None,
        scene_id: int = 1,
        panel_index: int = 0,
        style: str = None,
        action: str = "",
        panel_count: int = None,
        layout_type: str = None,
    ) -> str:
        """
        Generate an image based on style/prompts and save it to output_path.
        
        Returns:
            str: Path to the generated image file.
        """
        pass

    @abstractmethod
    def extract_character_anchor(self, image_path: str, output_path: str) -> str:
        """
        Extract character reference anchor from an image for continuity.
        
        Returns:
            str: Path to the extracted character reference image.
        """
        pass

    @abstractmethod
    def unload_model(self):
        """
        Unloads models from memory/VRAM to free up hardware resources.
        """
        pass
