import os
from fastapi import HTTPException
from sqlalchemy.orm import Session
from telegram_manager.db.models import TelegramAccount
import shutil
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telegram_manager.db.models import TelegramAccount
from telegram_manager.db.utils import commit_with_retry
from telegram_manager.core.config import settings
from telethon import Button



async def update_account_in_db(db: Session, phone_number: str, app_id: int = None, app_hash_id: str = None, session_file_path: str = None, bot_token: str = None):
    account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == phone_number).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if app_id is not None:
        account.app_id = app_id
    if app_hash_id is not None:
        account.app_hash_id = app_hash_id
    if session_file_path is not None:
        # Remove old session file if exists
        if account.session_file_path and os.path.exists(account.session_file_path):
            os.remove(account.session_file_path)
        account.session_file_path = session_file_path
    if bot_token is not None:
        account.bot_token = bot_token

    commit_with_retry(db)
    db.refresh(account)
    return account

async def delete_account_in_db(db: Session, phone_number: str):
    account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == phone_number).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Remove session file if exists
    if account.session_file_path and os.path.exists(account.session_file_path):
        os.remove(account.session_file_path)

    db.delete(account)
    commit_with_retry(db)


async def save_session_file(session_file: UploadFile, phone_number: str) -> str:
    session_dir = "session_files"
    os.makedirs(session_dir, exist_ok=True)
    session_file_path = os.path.join(session_dir, f"{phone_number}.session")
    with open(session_file_path, "wb") as buffer:
        shutil.copyfileobj(session_file.file, buffer)
    return session_file_path

async def create_account_in_db(db: Session, phone_number: str, app_id: int, app_hash_id: str, session_file_path: str, bot_token: str = None) -> TelegramAccount:
    new_account = TelegramAccount(
        phone_number=phone_number,
        app_id=app_id,
        app_hash_id=app_hash_id,
        session_file_path=session_file_path,
        bot_token=bot_token
    )
    db.add(new_account)
    commit_with_retry(db)
    db.refresh(new_account)
    return new_account

async def get_channels_for_account(db: Session, phone_number: str):
    account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == phone_number).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    proxy = None
    if settings.PROXY:
        # Expecting PROXY env var in format: "socks5,127.0.0.1,9050"
        parts = settings.PROXY.split(",")
        if len(parts) == 3:
            proxy = (parts[0], parts[1], int(parts[2]))

    client = TelegramClient(account.session_file_path, account.app_id, account.app_hash_id, proxy=proxy)
    await client.start()
    try:
        
        channels = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                channels.append({ "id": dialog.id, "name": dialog.name})
            
        await client.disconnect()
        return channels
    except SessionPasswordNeededError:
        await client.disconnect()
        raise HTTPException(status_code=403, detail="Two-step verification enabled, password required")
    except Exception as e:
        await client.disconnect()
        raise HTTPException(status_code=500, detail=str(e))
