import os
from typing import List, Optional
from providers.storage.base import StorageProvider
from providers.storage.local import LocalStorageProvider
from providers.storage.cloudflare_r2 import CloudflareR2StorageProvider
from providers.storage.supabase_storage import SupabaseStorageProvider

class StorageService:
    """
    Service class that routes all storage operations to the appropriate
    active StorageProvider based on the STORAGE_PROVIDER environment variable.
    Provides standard delegation and fallbacks.
    """
    
    def __init__(self):
        self.provider: StorageProvider = self._resolve_provider()

    def _resolve_provider(self) -> StorageProvider:
        provider_name = os.environ.get("STORAGE_PROVIDER", "local").strip().lower()
        print(f"[StorageService] Initializing with provider: '{provider_name}'")
        
        if provider_name == "local":
            return LocalStorageProvider()
        elif provider_name in ("cloudflare_r2", "r2"):
            return CloudflareR2StorageProvider()
        elif provider_name in ("supabase_storage", "supabase"):
            return SupabaseStorageProvider()
        else:
            print(f"[StorageService] Warning: Unknown storage provider '{provider_name}'. Falling back to 'local'.")
            return LocalStorageProvider()

    def save_image(self, image_bytes: bytes, filename: str, folder: Optional[str] = None) -> str:
        """Saves image bytes using the active storage provider."""
        return self.provider.save_image(image_bytes, filename, folder)

    def get_image(self, filename: str, folder: Optional[str] = None) -> bytes:
        """Retrieves raw image bytes using the active storage provider."""
        return self.provider.get_image(filename, folder)

    def delete_image(self, filename: str, folder: Optional[str] = None) -> bool:
        """Deletes the image using the active storage provider."""
        return self.provider.delete_image(filename, folder)

    def list_images(self, folder: Optional[str] = None) -> List[str]:
        """Lists images inside a folder using the active storage provider."""
        return self.provider.list_images(folder)

    def get_job_directory(self, timestamp: str) -> str:
        """Gets the job directory using the active storage provider."""
        return self.provider.get_job_directory(timestamp)

    def get_web_url(self, timestamp: str, filename: str) -> str:
        """Gets the web url using the active storage provider."""
        return self.provider.get_web_url(timestamp, filename)

# Singleton instance for global app usage
storage_service = StorageService()
