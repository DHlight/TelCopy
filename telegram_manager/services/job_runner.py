import logging
from sqlalchemy.orm import Session
from telegram_manager.db.models import TelegramJob, TelegramMessage, TelegramAccount
from telegram_manager.schemas.telegram_job import JobCreate
from telegram_manager.core.config import settings
from telethon import TelegramClient
import asyncio

logger = logging.getLogger("telegram_job_manager")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from telegram_manager.db.utils import commit_with_retry

from telegram_manager.db.models import JobTypeEnum, JobStatusEnum

# Global set to track running job tasks
running_job_tasks = set()

async def create_job_in_db(db: Session, job: JobCreate) -> TelegramJob:
    db_job = TelegramJob(
        source_account_id=job.source_account_id,
        source_channel=job.source_channel,
        dest_account_id=job.dest_account_id,
        dest_channel=job.dest_channel,
        job_type=job.job_type,
        status=JobStatusEnum.pending.value
    )
    db.add(db_job)
    commit_with_retry(db)
    db.refresh(db_job)
    return db_job

def run_async_job(coro_func, *args, **kwargs):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        asyncio.create_task(coro_func(*args, **kwargs))
    else:
        loop.run_until_complete(coro_func(*args, **kwargs))

async def run_full_job(job_id: int):
    logger.info(f"Starting full job with id: {job_id}")
    # TODO: Implement the full job logic here
    await asyncio.sleep(10)  # Simulate async work
    logger.info(f"Completed full job with id: {job_id}")

async def run_readtime_job(job_id: int):
    logger.info(f"Starting readtime job with id: {job_id}")
    # TODO: Implement the readtime job logic here
    await asyncio.sleep(10)  # Simulate async work
    logger.info(f"Completed readtime job with id: {job_id}")

async def schedule_job(db_job: TelegramJob):
    if db_job.job_type == JobTypeEnum.full.value:
        task = asyncio.create_task(run_full_job(db_job.id))
        running_job_tasks.add(task)
        task.add_done_callback(running_job_tasks.discard)
        await task
    elif db_job.job_type == JobTypeEnum.readtime.value:
        task = asyncio.create_task(run_readtime_job(db_job.id))
        running_job_tasks.add(task)
        task.add_done_callback(running_job_tasks.discard)
        await task
    else:
        logger.error(f"Invalid job_type: {db_job.job_type}")
        raise ValueError("Invalid job_type")

async def get_all_jobs(db: Session):
    jobs = db.query(TelegramJob).all()
    return jobs

def health_check():
    return {"status": "ok"}

async def delete_job_in_db(db: Session, job_id: int):
    job = db.query(TelegramJob).filter(TelegramJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job with id {job_id} not found")
    db.delete(job)
    db.commit()

async def health_check_job(job_id: int, db: Session):
    job = db.query(TelegramJob).filter(TelegramJob.id == job_id).first()
    if not job:
        return {"error": f"Job with id {job_id} not found"}
    return {"job_id": job_id, "status": job.status}

async def stop_job_in_db(db: Session, job_id: int):
    job = db.query(TelegramJob).filter(TelegramJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job with id {job_id} not found")
    job.status = "stopped"
    db.commit()

async def ensure_readtime_job_exists(db: Session):
    # Check if a readtime job exists and is not stopped
    readtime_job = db.query(TelegramJob).filter(
        TelegramJob.job_type == JobTypeEnum.readtime.value,
        TelegramJob.status != JobStatusEnum.stopped.value
    ).first()
    if not readtime_job:
        # Create a new readtime job with default values and status pending
        from telegram_manager.schemas.telegram_job import JobCreate
        # For required fields, use placeholders or defaults; adjust as needed
        new_job = JobCreate(
            source_account_id="default_source_account",
            source_channel=0,
            dest_account_id="default_dest_account",
            dest_channel=0,
            job_type=JobTypeEnum.readtime.value
        )
        await create_job_in_db(db, new_job)

async def load_and_schedule_jobs_on_startup():
    from telegram_manager.db.session import SessionLocal
    db = SessionLocal()
    try:
        # Cancel and clear existing running tasks to prevent duplicates
        for task in running_job_tasks:
            if not task.done():
                task.cancel()
        running_job_tasks.clear()

        await ensure_readtime_job_exists(db)

        jobs = db.query(TelegramJob).filter(TelegramJob.status.in_([JobStatusEnum.pending.value, JobStatusEnum.running.value,JobStatusEnum.failed.value])).all()
        jobs = [job for job in jobs if job.status != JobStatusEnum.stopped.value]
        # Schedule all jobs concurrently without awaiting each sequentially
        tasks = [asyncio.create_task(schedule_job(job)) for job in jobs]
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        db.close()

async def reload_and_schedule_all_jobs():
    from telegram_manager.db.session import SessionLocal
    db = SessionLocal()
    try:
        # Cancel and clear existing running tasks to prevent duplicates
        for task in running_job_tasks:
            if not task.done():
                task.cancel()
        running_job_tasks.clear()

        jobs = db.query(TelegramJob).filter(TelegramJob.status.in_([JobStatusEnum.pending.value, JobStatusEnum.running.value,JobStatusEnum.failed.value])).all()
        jobs = [job for job in jobs if job.status != JobStatusEnum.stopped.value]
        # Schedule all jobs concurrently without awaiting each sequentially
        tasks = [asyncio.create_task(schedule_job(job)) for job in jobs]
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        db.close()
