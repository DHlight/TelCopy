from fastapi import FastAPI
from app.api.accounts import router as accounts_router
from app.api.messages import router as messages_router
from app.db import database, models
from app.core.scheduler import scheduler, start_scheduler
import asyncio

app = FastAPI()

app.include_router(accounts_router)
app.include_router(messages_router)

@app.on_event("startup")
async def load_saved_jobs():
    db = database.SessionLocal()
    try:
        jobs = db.query(models.MessageJob).all()
        from app.telegram.client import TelegramAccountManager
        from app.telegram.message_handler import handle_telegram_message
        account_manager = TelegramAccountManager()

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
