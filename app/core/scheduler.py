from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.db.database import DATABASE_URL
from app.db import database, models
from app.telegram.client import TelegramAccountManager
from app.telegram.message_handler import handle_telegram_message

jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL)
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()

def reload_jobs():
    db = database.SessionLocal()
    try:
        jobs = db.query(models.MessageJob).all()
        account_manager = TelegramAccountManager()

        scheduler.remove_all_jobs()

        for job in jobs:
            in_account_id = job.in_account_id
            out_account_id = job.out_account_id
            input_channel = job.input_channel
            output_channel = job.output_channel

            client = account_manager.clients.get(in_account_id)

            if client:
                async def message_handler(event):
                    await handle_telegram_message(in_account_id, out_account_id, output_channel, event)

                def job_func():
                    client.add_event_handler(message_handler, client.events.NewMessage(chats=input_channel))

                scheduler.add_job(job_func, id=job.job_id, replace_existing=True)

        start_scheduler()
    finally:
        db.close()

def remove_job(job_id: str):
    if scheduler.get_job(job_id):
