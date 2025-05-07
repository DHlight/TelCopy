from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Path, status
from sqlalchemy.orm import Session
from telegram_manager.db.session import get_db
from telegram_manager.db.models import TelegramJob
from telegram_manager.schemas.telegram_job import JobCreate, JobResponse
from telegram_manager.services.job_runner import (
    create_job_in_db,
    get_all_jobs,
    health_check,
    delete_job_in_db,
    health_check_job,
    stop_job_in_db,
    run_full_job,
    run_readtime_job,
    stop_all_jobs_in_db,
)
from telegram_manager.core.config import settings

import logging
from telegram_manager.schemas.telegram_job import JobResponse

router = APIRouter()

@router.get("/", response_model=list[JobResponse])
async def get_jobs(db: Session = Depends(get_db)):
    jobs = await get_all_jobs(db)
    # Convert each job to JobResponse with status as int
    return [JobResponse.from_orm(job).copy(update={"status": job.status_int}) for job in jobs]

@router.post("/", response_model=JobResponse)
async def create_job(job: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_job = await create_job_in_db(db, job)
    if db_job.job_type == 0:
        background_tasks.add_task(run_full_job, db_job.id)
    elif db_job.job_type == 1:
        background_tasks.add_task(run_readtime_job, db_job.id)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job type")
    return JobResponse.from_orm(db_job).copy(update={"status": db_job.status_int})

@router.get("/health")
async def health_check_endpoint():
    return health_check()

@router.get("/health/{job_id}")
async def health_check_job_endpoint(job_id: int = Path(..., description="The ID of the job to check"), db: Session = Depends(get_db)):
    result = await health_check_job(job_id, db)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result

@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: int, db: Session = Depends(get_db)):
    try:
        await delete_job_in_db(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return

@router.post("/stop/{job_id}", status_code=status.HTTP_200_OK)
async def stop_job(job_id: int, db: Session = Depends(get_db)):
    try:
        await stop_job_in_db(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"message": f"Job {job_id} stopped successfully"}

@router.post("/reload_all", status_code=status.HTTP_200_OK)
async def reload_all_jobs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from telegram_manager.services.job_runner import reload_and_schedule_all_jobs
    import asyncio
    # Run the reload_and_schedule_all_jobs asynchronously without blocking
    asyncio.create_task(reload_and_schedule_all_jobs())
    return {"message": "All jobs reloaded and scheduled successfully"}

@router.post("/run/{job_id}", status_code=status.HTTP_200_OK)
async def run_job_directly(job_id: int, db: Session = Depends(get_db)):
    job = db.query(TelegramJob).filter(TelegramJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with id {job_id} not found")
    from telegram_manager.services.job_runner import run_async_job
    import asyncio
    if job.job_type == 0:
        asyncio.create_task(run_full_job(job_id))
    elif job.job_type == 1:
        asyncio.create_task(run_readtime_job(job_id))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job type")
    return {"message": f"Job {job_id} started directly"}

@router.post("/stop_all", status_code=status.HTTP_200_OK)
async def stop_all_jobs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        await stop_all_jobs_in_db()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return {"message": "All jobs stopped successfully"}

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(TelegramJob).filter(TelegramJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with id {job_id} not found")
    return JobResponse.from_orm(job).copy(update={"status": job.status_int})
