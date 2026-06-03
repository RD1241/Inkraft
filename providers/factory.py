import os
from config import settings
from providers.llm.base import LLMProvider
from providers.llm.ollama import OllamaLLMProvider
from providers.llm.groq import GroqLLMProvider
from providers.image.base import ImageProvider
from providers.image.stable_diffusion import StableDiffusionImageProvider
from providers.image.fal_ai import FalAIImageProvider
from providers.image.replicate import ReplicateImageProvider
from providers.storage.base import StorageProvider
from providers.storage.local import LocalStorageProvider

def get_llm_provider() -> LLMProvider:
    """
    Returns the active LLMProvider instance determined by the LLM_PROVIDER env variable.
    """
    provider_name = os.environ.get("LLM_PROVIDER", "ollama").lower()
    if provider_name == "ollama":
        return OllamaLLMProvider()
    elif provider_name == "groq":
        return GroqLLMProvider()
    else:
        print(f"[Warning] Unknown LLM_PROVIDER '{provider_name}', falling back to OllamaLLMProvider.")
        return OllamaLLMProvider()

def get_image_provider() -> ImageProvider:
    """
    Returns the active ImageProvider instance determined by the IMAGE_PROVIDER env variable.
    """
    provider_name = os.environ.get("IMAGE_PROVIDER", "stable_diffusion").lower()
    if provider_name == "stable_diffusion":
        return StableDiffusionImageProvider()
    elif provider_name == "fal_ai":
        return FalAIImageProvider()
    elif provider_name == "replicate":
        return ReplicateImageProvider()
    else:
        print(f"[Warning] Unknown IMAGE_PROVIDER '{provider_name}', falling back to StableDiffusionImageProvider.")
        return StableDiffusionImageProvider()

def get_storage_provider() -> StorageProvider:
    """
    Returns the active StorageProvider instance determined by the STORAGE_PROVIDER env variable.
    """
    provider_name = os.environ.get("STORAGE_PROVIDER", "local").lower()
    if provider_name == "local":
        return LocalStorageProvider()
    else:
        # Fallback to local storage provider for now
        print(f"[Warning] Unknown STORAGE_PROVIDER '{provider_name}', falling back to LocalStorageProvider.")
        return LocalStorageProvider()
