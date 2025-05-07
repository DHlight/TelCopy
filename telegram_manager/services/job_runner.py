import logging
from sqlalchemy.orm import Session
from telegram_manager.db.models import TelegramJob, TelegramMessage, TelegramAccount, JobTypeEnum, JobStatusEnum
from telegram_manager.schemas.telegram_job import JobCreate
from telegram_manager.core.config import settings
from telethon import TelegramClient, events
import asyncio
from telegram_manager.db.session import SessionLocal

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

    db = SessionLocal()
    source_client = None
    dest_client = None
    try:
        logger.info(f"run_readtime_job: fetching job with id {job_id}")
        # Fetch job details from DB
        job = db.query(TelegramJob).filter(TelegramJob.id == job_id).first()
        if not job:
            logger.error(f"Job with id {job_id} not found")
            return

        # Fetch source account details
        source_account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == job.source_account_id).first()
        if not source_account:
            logger.error(f"Source account {job.source_account_id} not found")
            return

        # Fetch destination account details
        dest_account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == job.dest_account_id).first()
        if not dest_account:
            logger.error(f"Destination account {job.dest_account_id} not found")
            return

        # Create Telegram clients for source and destination
        if source_account.session_file_path == dest_account.session_file_path:
            logger.error("Source and destination accounts have the same session file. This can cause Telethon session conflicts.")
            raise ValueError("Source and destination accounts must have distinct session files.")

        source_client = TelegramClient(source_account.session_file_path, source_account.app_id, source_account.app_hash_id)
        dest_client = TelegramClient(dest_account.session_file_path, dest_account.app_id, dest_account.app_hash_id)

        await source_client.start()
        await dest_client.start()

        # Event handler for new messages on source channel
        @source_client.on(events.NewMessage(chats=job.source_channel))
        async def handler(event):
            try:
                message = event.message
                # Prepare forwarding with job id info
                job_info_text = f"[Forwarded by job id: {job_id}]"

                # Check message type and forward accordingly
                if message.media:
                    # Media or multi-media message
                    # Forward media with caption including job id info
                    caption = (message.text or "") + "\n" + job_info_text
                    await dest_client.send_file(
                        job.dest_channel,
                        file=message.media,
                        caption=caption
                    )
                else:
                    # Text message
                    text = (message.text or "") + "\n" + job_info_text
                    await dest_client.send_message(job.dest_channel, text)
                logger.info(f"Forwarded message from {job.source_channel} to {job.dest_channel} for job {job_id}")
            except Exception as e:
                logger.error(f"Error forwarding message in job {job_id}: {e}")

        # Keep the clients running and listening until cancelled
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info(f"Readtime job with id: {job_id} has been cancelled")
    except Exception as e:
        logger.error(f"Exception in readtime job {job_id}: {e}")
    finally:
        await source_client.disconnect()
        await dest_client.disconnect()
        db.close()
        logger.info(f"Exiting readtime job with id: {job_id}")

async def schedule_job(db_job: TelegramJob):
    if db_job.job_type == JobTypeEnum.full.value:
        task = asyncio.create_task(run_full_job(db_job.id))
        running_job_tasks.add(task)
        task.add_done_callback(running_job_tasks.discard)
        await task
    elif db_job.job_type == JobTypeEnum.readtime.value:
        while True:
            try:
                task = asyncio.create_task(run_readtime_job(db_job.id))
                running_job_tasks.add(task)
                task.add_done_callback(running_job_tasks.discard)
                await task
            except Exception as e:
                logger.error(f"Readtime job {db_job.id} failed with exception: {e}. Restarting...")
                await asyncio.sleep(5)  # Wait before retrying
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

# Removed ensure_readtime_job_exists function as per user request

async def load_and_schedule_jobs_on_startup():
    from telegram_manager.db.session import SessionLocal
    db = SessionLocal()
    try:
        # Cancel and clear existing running tasks to prevent duplicates
        for task in running_job_tasks:
            if not task.done():
                task.cancel()
        running_job_tasks.clear()

        # Removed call to ensure_readtime_job_exists as it no longer exists

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
