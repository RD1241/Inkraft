import os
from typing import List, Optional
from config import settings
from providers.storage.base import StorageProvider

class LocalStorageProvider(StorageProvider):
    """
    Local filesystem implementation of StorageProvider.
    Saves files to the local outputs directory and returns web-accessible relative paths.
    """

    def __init__(self):
        self.base_dir = settings.OUTPUTS_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_absolute_path(self, filename: str, folder: Optional[str] = None) -> str:
        if folder:
            target_dir = os.path.join(self.base_dir, folder)
            os.makedirs(target_dir, exist_ok=True)
            return os.path.join(target_dir, filename)
        return os.path.join(self.base_dir, filename)

    def _get_relative_path(self, filename: str, folder: Optional[str] = None) -> str:
        if folder:
            return f"/outputs/{folder}/{filename}"
        return f"/outputs/{filename}"

    def save_image(self, image_bytes: bytes, filename: str, folder: Optional[str] = None) -> str:
        abs_path = self._get_absolute_path(filename, folder)
        with open(abs_path, "wb") as f:
            f.write(image_bytes)
        return self._get_relative_path(filename, folder)

    def get_image(self, filename: str, folder: Optional[str] = None) -> bytes:
        abs_path = self._get_absolute_path(filename, folder)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Image not found at path: {abs_path}")
        with open(abs_path, "rb") as f:
            return f.read()

    def delete_image(self, filename: str, folder: Optional[str] = None) -> bool:
        abs_path = self._get_absolute_path(filename, folder)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
                return True
            except Exception as e:
                print(f"[Storage] Failed to delete local image: {e}")
                return False
        return False

    def list_images(self, folder: Optional[str] = None) -> List[str]:
        target_dir = os.path.join(self.base_dir, folder) if folder else self.base_dir
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            return []
        
        files = []
        for file in os.listdir(target_dir):
            if os.path.isfile(os.path.join(target_dir, file)) and file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                files.append(self._get_relative_path(file, folder))
        return files

    def get_job_directory(self, timestamp: str) -> str:
        """Returns absolute path to the local job output directory."""
        directory = os.path.join(self.base_dir, timestamp)
        os.makedirs(directory, exist_ok=True)
        return directory

    def get_web_url(self, timestamp: str, filename: str) -> str:
        """Returns the local web relative path for the output file."""
        return f"/outputs/{timestamp}/{filename}"
