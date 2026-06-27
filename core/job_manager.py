import os
from config import settings
from services.job_service import JobService

class JobManager:
    """
    JobManager acts as a backward-compatible wrapper delegating to JobService.
    All DB initialization, Supabase synchronization, and progress percentage Calculations
    are handled by JobService in services/job_service.py.
    """
    def __init__(self, db_path=None):
        # Resolve base DB path
        resolved_db_path = db_path or os.path.join(settings.DB_DIR, "jobs.db")
        # Delegate to the newly created JobService
        self.job_service = JobService(resolved_db_path)

    def create_job(self, panel_count: int = None, layout_type: str = None, panel_count_mode: str = None, generation_format: str = None, user_id: str = None) -> str:
        return self.job_service.create_job(
            panel_count=panel_count,
            layout_type=layout_type,
            panel_count_mode=panel_count_mode,
            generation_format=generation_format,
            user_id=user_id
        )

    def update_job(self, job_id: str, status: str, result: str = None, error: str = None, progress: str = None):
        self.job_service.update_job(
            job_id=job_id,
            status=status,
            result=result,
            error=error,
            progress=progress
        )

    def get_job(self, job_id: str) -> dict:
        return self.job_service.get_job(job_id)
