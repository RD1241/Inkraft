from providers.image.base import ImageProvider
from core.sd_generator import SDGenerator

class StableDiffusionImageProvider(ImageProvider):
    def __init__(self, model_id: str = None):
        """
        Initializes the Stable Diffusion image provider.
        """
        self.generator = SDGenerator(model_id=model_id)

    def create_base_latents(self, seed: int = 42):
        """
        Delegates base latents generation to SDGenerator.
        """
        return self.generator.create_base_latents(seed)

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
        panel_width: int = 768,
        panel_height: int = 1024,
        focus_character: str = "",
        secondary_character: str = "",
        job_id: str = "",
    ) -> str:
        """
        Delegates image generation to SDGenerator.
        """
        return self.generator.generate_image(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            output_path=output_path,
            seed=seed,
            reference_image_path=reference_image_path,
            reference_strength=reference_strength,
            base_latents=base_latents,
            scene_id=scene_id,
            panel_index=panel_index,
            style=style,
            action=action,
            panel_count=panel_count,
            layout_type=layout_type,
            panel_width=panel_width,
            panel_height=panel_height,
            focus_character=focus_character,
            job_id=job_id,
        )

    def extract_character_anchor(self, image_path: str, output_path: str) -> str:
        """
        Delegates character anchor extraction to SDGenerator.
        """
        return self.generator.extract_character_anchor(image_path, output_path)

    def unload_model(self):
        """
        Delegates model unloading to SDGenerator.
        """
        self.generator.unload_model()
