import logging
from sqlalchemy.orm import Session
from telegram_manager.db.models import TelegramJob, TelegramMessage, TelegramAccount, JobTypeEnum, JobStatusEnum
from telegram_manager.schemas.telegram_job import JobCreate
from telegram_manager.core.config import settings
from telethon import TelegramClient, events
import asyncio
from telegram_manager.db.session import SessionLocal
import os

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
        status=JobStatusEnum.pending.value,
        filter_user_id=getattr(job, 'filter_user_id', None)
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

import shutil
import tempfile

async def run_full_job(job_id: int):
    logger.info(f"Starting full job with id: {job_id}")
    # TODO: Implement the full job logic here

    # Example: clone base session file to job-specific session file
    # This is a placeholder, adjust according to actual session file usage
    base_session_file = "session_files/base.session"
    job_session_file = f"session_files/{job_id}_base.session"
    try:
        shutil.copy(base_session_file, job_session_file)
        logger.info(f"Cloned session file for job {job_id}: {job_session_file}")
        # Use job_session_file in TelegramClient or job logic here

        await asyncio.sleep(10)  # Simulate async work

    finally:
        # Remove the cloned session file after job completes
        if os.path.exists(job_session_file):
            os.remove(job_session_file)
            logger.info(f"Removed session file for job {job_id}: {job_session_file}")

    logger.info(f"Completed full job with id: {job_id}")

async def run_readtime_job(job_id: int):


    logger.info(f"Starting readtime job with id: {job_id}")

    db = SessionLocal()
    source_client = None
    dest_client = None

    # Clone session files for this job
    def clone_session_file(original_path: str, job_id: int) -> str:
        if not original_path or not os.path.exists(original_path):
            return original_path
        base_name = os.path.basename(original_path)
        new_name = f"{job_id}_{base_name}"
        new_path = os.path.join(os.path.dirname(original_path), new_name)
        shutil.copy(original_path, new_path)
        logger.info(f"Cloned session file from {original_path} to {new_path}")
        return new_path

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

        proxy = None
        if settings.PROXY:
            parts = settings.PROXY.split(",")
            if len(parts) == 3:
                proxy = (parts[0], parts[1], int(parts[2]))

        # Clone session files for source and destination accounts
        source_session_file = clone_session_file(source_account.session_file_path, job_id)
        dest_session_file = clone_session_file(dest_account.session_file_path, job_id)

        source_client = TelegramClient(source_session_file, source_account.app_id, source_account.app_hash_id, proxy=proxy)
        await source_client.start()

        if dest_account.bot_token:
            dest_client = TelegramClient('bot_' + dest_account.phone_number, dest_account.app_id, dest_account.app_hash_id, proxy=proxy)
            await dest_client.start(bot_token=dest_account.bot_token)
        else:
            dest_client = TelegramClient(dest_session_file, dest_account.app_id, dest_account.app_hash_id, proxy=proxy)
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
                    # Check for unsupported media types (e.g., games)
                    if hasattr(message.media, 'document') and message.media.document.mime_type == 'application/x-tgsticker':
                        # Skip unsupported media type
                        logger.warning(f"Skipping unsupported media type in job {job_id}")
                    else:
                        # Forward media with caption including job id info
                        caption = (message.text or "") + "\n" + job_info_text
                        downloads_dir = "downloads"
                        os.makedirs(downloads_dir, exist_ok=True)

                        file_path = await message.download_media(file=downloads_dir)

                        await dest_client.send_file(
                            job.dest_channel,
                            file=file_path,
                            caption=caption
                        )
                else:
                    # Text message
                    text = (message.text or "") + "\n" + job_info_text
                    await dest_client.send_message(job.dest_channel, text)
                logger.info(f"Forwarded message from {job.source_channel} to {job.dest_channel} for job {job_id}")
            except Exception as e:
                logger.error(f"Error forwarding message in job {job_id}: {e}")
                logger.error(f"Message content: {message}")

        # Keep the clients running and listening until cancelled
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info(f"Readtime job with id: {job_id} has been cancelled")
    except Exception as e:
        logger.error(f"Exception in readtime job {job_id}: {e}")
    finally:
        if source_client:
            await source_client.disconnect()
        if dest_client:
            await dest_client.disconnect()
        db.close()

        # Remove cloned session files
        def remove_session_file(path: str):
            if path and os.path.exists(path) and not path.endswith("base.session"):
                try:
                    os.remove(path)
                    logger.info(f"Removed session file: {path}")
                except Exception as e:
                    logger.error(f"Failed to remove session file {path}: {e}")

        remove_session_file(source_session_file)
        remove_session_file(dest_session_file)

        logger.info(f"Exiting readtime job with id: {job_id}")

async def run_clean_job(job_id: int):
    logger.info(f"Starting clean job with id: {job_id}")
    # TODO: Implement the cleaning logic here
    # For example, connect to TelegramClient, check channels/groups where user is admin, and clean messages
    await asyncio.sleep(10)  # Simulate async work
    logger.info(f"Completed clean job with id: {job_id}")

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
    elif db_job.job_type == JobTypeEnum.clean.value:
        task = asyncio.create_task(run_clean_job(db_job.id))
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

    # Stop the job by setting status to stopped
    from telegram_manager.db.models import JobStatusEnum
    job.status = JobStatusEnum.stopped.value
    db.commit()

    # Cancel running async tasks related to this job
    to_cancel = []
    for task in running_job_tasks:
        if not task.done():
            # Check if the task is for this job_id by inspecting the coroutine
            coro = task.get_coro()
            if hasattr(coro, 'cr_frame') and coro.cr_frame is not None:
                # Try to get job_id from coroutine frame locals
                frame_locals = coro.cr_frame.f_locals
                if 'job_id' in frame_locals and frame_locals['job_id'] == job_id:
                    to_cancel.append(task)
    for task in to_cancel:
        task.cancel()
        running_job_tasks.discard(task)

    # Now delete the job from DB
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
    from telegram_manager.db.models import JobStatusEnum
    job.status = JobStatusEnum.stopped.value
    db.commit()

    # Cancel running async tasks related to this job
    to_cancel = []
    for task in running_job_tasks:
        if not task.done():
            # Check if the task is for this job_id by inspecting the coroutine
            coro = task.get_coro()
            if hasattr(coro, 'cr_frame') and coro.cr_frame is not None:
                # Try to get job_id from coroutine frame locals
                frame_locals = coro.cr_frame.f_locals
                if 'job_id' in frame_locals and frame_locals['job_id'] == job_id:
                    to_cancel.append(task)
    for task in to_cancel:
        task.cancel()

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

async def stop_all_jobs_in_db():
    from telegram_manager.db.session import SessionLocal
    from telegram_manager.db.models import JobStatusEnum
    db = SessionLocal()
    try:
        # Cancel all running tasks
        to_cancel = [task for task in running_job_tasks if not task.done()]
        for task in to_cancel:
            task.cancel()
            running_job_tasks.discard(task)

        # Update all jobs status to stopped
        jobs = db.query(TelegramJob).filter(TelegramJob.status != JobStatusEnum.stopped.value).all()
        for job in jobs:
            job.status = JobStatusEnum.stopped.value
        db.commit()
    finally:
        db.close()
