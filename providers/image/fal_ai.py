import os
import httpx
from PIL import Image
from config import settings
from providers.image.base import ImageProvider

# Style-to-model mapping for fal.ai endpoints
STYLE_MODEL_MAP = {
    "manga": {"endpoint": "fal-ai/fast-animagine-xl"},
    "manhwa": {"endpoint": "fal-ai/any-sdxl", "model_name": "Linaqruf/noobai-xl-v1.0"},
    "anime": {"endpoint": "fal-ai/fast-animagine-xl"},
    "cinematic": {"endpoint": "fal-ai/fast-sdxl", "model_name": "Lykon/dreamshaper-xl-v2-turbo"},
    "realistic": {"endpoint": "fal-ai/realistic-vision"},
}

class FalAIImageProvider(ImageProvider):
    def __init__(self, api_key: str = None):
        """
        Initializes the Fal AI image provider.
        """
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if self.api_key:
            os.environ["FAL_KEY"] = self.api_key

    def create_base_latents(self, seed: int = 42):
        """
        Fal AI API does not consume raw base noise latents directly.
        Returns None.
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
        panel_count: int = None,
        layout_type: str = None,
    ) -> str:
        """
        Generates an image via the fal.ai API using fal_client.
        Falls back to local StableDiffusionImageProvider on any API error.
        """
        try:
            import fal_client

            # Ensure API key is set for client authentication
            if not os.environ.get("FAL_KEY"):
                raise ValueError("FAL_KEY environment variable is not set")

            # Route style to model configuration
            style_key = style.lower() if style else "anime"
            if style_key not in STYLE_MODEL_MAP:
                print(f"[FalAI] Style '{style}' not recognized, falling back to 'anime'")
                style_key = "anime"

            model_config = STYLE_MODEL_MAP[style_key]
            endpoint = model_config["endpoint"]
            model_log_name = model_config.get("model_name", endpoint)

            # Set up parameters
            arguments = {
                "prompt": positive_prompt,
                "negative_prompt": negative_prompt,
                "seed": seed,
                "image_size": {
                    "width": getattr(settings, "SD_WIDTH", 512),
                    "height": getattr(settings, "SD_HEIGHT", 512),
                }
            }

            # Add model_name parameter for checkpoints routed via general/dynamic endpoints
            if "model_name" in model_config:
                arguments["model_name"] = model_config["model_name"]

            # Handle character consistency / reference image
            if reference_image_path and os.path.exists(reference_image_path):
                # Upload the local reference image to fal.ai CDN to get public URL
                image_url = fal_client.upload_file(reference_image_path)

                if style_key == "realistic":
                    # realistic-vision (SD 1.5) supports ControlNet pose reference
                    arguments["control_image_url"] = image_url
                    if reference_strength is not None:
                        arguments["controlnet_conditioning_scale"] = reference_strength
                else:
                    # SDXL models take image_url for image-to-image or IP Adapter reference
                    arguments["image_url"] = image_url
                    if reference_strength is not None:
                        arguments["strength"] = reference_strength

            # Call the fal.ai API endpoint synchronously
            result = fal_client.subscribe(endpoint, arguments)

            if not result or "images" not in result or len(result["images"]) == 0:
                raise ValueError("Empty image response from fal.ai API")

            generated_image_url = result["images"][0]["url"]

            # Download generated image and save to destination path
            response = httpx.get(generated_image_url)
            response.raise_for_status()

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)

            # Cost tracking log
            print(f"[FalAI] Panel generated — model: {model_log_name}, estimated cost: $0.003")
            return output_path

        except Exception as error:
            # Fall back to local StableDiffusionImageProvider gracefully
            print(f"[FalAI] API call failed: {error} — falling back to local SD")
            from providers.image.stable_diffusion import StableDiffusionImageProvider
            local_provider = StableDiffusionImageProvider()
            return local_provider.generate_image(
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
            )

    def extract_character_anchor(self, image_path: str, output_path: str) -> str:
        """
        Extracts character reference anchor from an image locally using PIL and saves it to output_path.
        """
        image  = Image.open(image_path).convert("RGB")
        w, h   = image.size
        cw, ch = int(w * 0.60), int(h * 0.80)
        l      = max((w - cw) // 2, 0)
        t      = max((h - ch) // 2, 0)
        anchor = image.crop((l, t, min(l + cw, w), min(t + ch, h))).resize(
            (getattr(settings, "SD_WIDTH", 512), getattr(settings, "SD_HEIGHT", 512)), Image.Resampling.LANCZOS
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        anchor.save(output_path)
        return output_path

    def unload_model(self):
        """
        No-op for API-based provider.
        """
        print("[FalAIImageProvider] Unloading model (no-op for API)")
