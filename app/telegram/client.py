from telethon import TelegramClient, events
from app.db import models, database
from sqlalchemy.orm import Session
import asyncio

class TelegramAccountManager:
    def __init__(self):
        self.clients = {}

    async def start_client(self, account: models.TelegramAccount):
        session_path = f"sessions/{account.phone_number}"
        client = TelegramClient(session_path, int(account.api_id), account.api_hash)
        await client.start()
        self.clients[account.id] = client

        @client.on(events.NewMessage(chats=None))
        async def handler(event):
            # Save message to DB
            async with database.SessionLocal() as session:
                db: Session = session
                message = models.Message(
                    account_id=account.id,
                    message_id=str(event.message.id),
                    content=event.message.message,
                    read=False
                )
                db.add(message)
                db.commit()

    async def send_message(self, account_id: int, channel: str, message: str):
        client = self.clients.get(account_id)
        if client:
            await client.send_message(channel, message)

    async def stop_client(self, account_id: int):
        client = self.clients.get(account_id)
        if client:
            await client.disconnect()
            del self.clients[account_id]
