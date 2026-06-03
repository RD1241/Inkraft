from providers.image.base import ImageProvider

class ReplicateImageProvider(ImageProvider):
    def __init__(self, api_key: str = None):
        """
        Initializes the Replicate image provider stub.
        """
        self.api_key = api_key

    def create_base_latents(self, seed: int = 42):
        """
        Replicate stub for creating base noise latents.
        """
        return None

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
    ) -> str:
        """
        Replicate stub for generating panel image.
        """
        print(f"[ReplicateImageProvider] STUB: Generating image for scene {scene_id} via Replicate at {output_path}")
        return output_path

    def extract_character_anchor(self, image_path: str, output_path: str) -> str:
        """
        Replicate stub for extracting character anchor.
        """
        print(f"[ReplicateImageProvider] STUB: Extracting character anchor from {image_path} to {output_path}")
        return output_path

    def unload_model(self):
        """
        Replicate stub for unloading models.
        """
        print("[ReplicateImageProvider] STUB: Unloading model")
