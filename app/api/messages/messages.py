from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import models, database
from app.telegram.client import TelegramAccountManager
from app.schemas import schemas
from app.core.scheduler import scheduler, start_scheduler
import asyncio

router = APIRouter()

account_manager = TelegramAccountManager()

async def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/jobs/")
async def create_message_job(
    in_account_id: int,
    out_account_id: int,
    input_channel: str,
    output_channel: str,
    db: Session = Depends(get_db)
):
    from app.core.scheduler import reload_jobs

    in_client = account_manager.clients.get(in_account_id)
    if not in_client:
        raise HTTPException(status_code=404, detail=f"Telegram client for account {in_account_id} not found")

    async def handle_new_message(event):
        message = models.Message(
            account_id=in_account_id,
            message_id=str(event.message.id),
            content=event.message.message,
            read=False
        )
        db.add(message)
        db.commit()

        out_client = account_manager.clients.get(out_account_id)
        if out_client:
            await out_client.send_message(output_channel, event.message.message)

        message.read = True
        db.commit()

    def job():
        in_client.add_event_handler(handle_new_message, in_client.events.NewMessage(chats=input_channel))

    # Save job info to DB for persistence
    from app.db.models import MessageJob
    job_id = f"message_job_{in_account_id}_{out_account_id}_{input_channel}_{output_channel}"
    existing_job = db.query(MessageJob).filter(MessageJob.job_id == job_id).first()
    if not existing_job:
        new_job = MessageJob(
            job_id=job_id,
            in_account_id=in_account_id,
            out_account_id=out_account_id,
            input_channel=input_channel,
            output_channel=output_channel
        )
        db.add(new_job)
        db.commit()

    reload_jobs()

    return {
        "detail": f"Background job scheduled and saved for accounts {in_account_id} -> {out_account_id} from {input_channel} to {output_channel}"
    }
