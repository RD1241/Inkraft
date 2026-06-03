from typing import List, Optional
from providers.storage.base import StorageProvider

class CloudflareR2StorageProvider(StorageProvider):
    """
    Cloudflare R2 implementation of StorageProvider.
    Currently a stub that raises NotImplementedError.
    """

    def save_image(self, image_bytes: bytes, filename: str, folder: Optional[str] = None) -> str:
        raise NotImplementedError("Cloudflare R2 Storage Provider is not implemented yet.")

    def get_image(self, filename: str, folder: Optional[str] = None) -> bytes:
        raise NotImplementedError("Cloudflare R2 Storage Provider is not implemented yet.")

    def delete_image(self, filename: str, folder: Optional[str] = None) -> bool:
        raise NotImplementedError("Cloudflare R2 Storage Provider is not implemented yet.")

    def list_images(self, folder: Optional[str] = None) -> List[str]:
        raise NotImplementedError("Cloudflare R2 Storage Provider is not implemented yet.")

    def get_job_directory(self, timestamp: str) -> str:
        raise NotImplementedError("Cloudflare R2 Storage Provider is not implemented yet.")

    def get_web_url(self, timestamp: str, filename: str) -> str:
        raise NotImplementedError("Cloudflare R2 Storage Provider is not implemented yet.")
