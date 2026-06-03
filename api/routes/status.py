from fastapi import APIRouter, HTTPException
from services.comic_service import comic_service
import sqlite3

router = APIRouter()

@router.get("/status/{job_id}")
def get_job_status(job_id: str):
    job = comic_service.job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Enrich with comic_id if job is completed
    if job and job.get("status") == "completed":
        try:
            from services.history_service import history_service
            conn = sqlite3.connect(history_service.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM comics WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                job["comic_id"] = row[0]
                if isinstance(job.get("result"), dict):
                    job["result"]["comic_id"] = row[0]
        except Exception as e:
            print(f"[Warning] Failed to enrich status with comic_id: {e}")
            
    return job
