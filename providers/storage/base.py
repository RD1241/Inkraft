from abc import ABC, abstractmethod
from typing import List, Optional

class StorageProvider(ABC):
    """
    Abstract base class defining the interface for all image storage providers.
    Allows hot-swapping between local, Cloudflare R2, and Supabase Storage.
    """

    @abstractmethod
    def save_image(self, image_bytes: bytes, filename: str, folder: Optional[str] = None) -> str:
        """
        Saves image bytes to the storage provider.
        
        Args:
            image_bytes: Raw bytes of the image to be saved.
            filename: The name of the file to save.
            folder: Optional subfolder/directory within storage.
            
        Returns:
            str: The public URL or relative path of the saved image.
        """
        pass

    @abstractmethod
    def get_image(self, filename: str, folder: Optional[str] = None) -> bytes:
        """Retrieves raw image bytes from storage."""
        pass

    @abstractmethod
    def delete_image(self, filename: str, folder: Optional[str] = None) -> bool:
        """Deletes the image from storage."""
        pass

    @abstractmethod
    def list_images(self, folder: Optional[str] = None) -> List[str]:
        """Lists filenames/relative paths of all images in a folder."""
        pass

    @abstractmethod
    def get_job_directory(self, timestamp: str) -> str:
        """Gets the job directory path where outputs are stored."""
        pass

    @abstractmethod
    def get_web_url(self, timestamp: str, filename: str) -> str:
        """Gets the web-accessible URL for an output file."""
        pass
