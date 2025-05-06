from app.db import models, database
from app.telegram.client import TelegramAccountManager

account_manager = TelegramAccountManager()

async def handle_telegram_message(in_account_id: int, out_account_id: int, output_channel: str, event):
    db = database.SessionLocal()
    try:
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
    finally:
        db.close()
