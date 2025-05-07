from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from telegram_manager.db.session import get_db
from telegram_manager.db.models import TelegramAccount
from telegram_manager.services.telegram_client import (
    save_session_file,
    create_account_in_db,
    get_channels_for_account,
)
import os

router = APIRouter()

@router.get("/")
async def get_accounts(db: Session = Depends(get_db)):
    accounts = db.query(TelegramAccount).all()
    return {"accounts": [{"phone_number": acc.phone_number, "app_id": acc.app_id, "app_hash_id": acc.app_hash_id} for acc in accounts]}

@router.post("/")
async def create_account(
    phone_number: str = Form(...),
    app_id: int = Form(...),
    app_hash_id: str = Form(...),
    session_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Check if account already exists
    existing_account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == phone_number).first()
    if existing_account:
        raise HTTPException(status_code=400, detail="Account with this phone number already exists")

    # Save the uploaded session file
    session_file_path = await save_session_file(session_file, phone_number)

    # Create new account record
    new_account = await create_account_in_db(db, phone_number, app_id, app_hash_id, session_file_path)

    return {"message": "Account created successfully", "phone_number": new_account.phone_number}

@router.get("/channels/{phone_number}")
async def get_channels(phone_number: str, db: Session = Depends(get_db)):
    channels = await get_channels_for_account(db, phone_number)
    return {"channels": channels}

@router.put("/{phone_number}")
async def update_account(
    phone_number: str,
    app_id: int = Form(None),
    app_hash_id: str = Form(None),
    session_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Check if account exists
    existing_account = db.query(TelegramAccount).filter(TelegramAccount.phone_number == phone_number).first()
    if not existing_account:
        raise HTTPException(status_code=404, detail="Account not found")

    session_file_path = None
    if session_file:
        from telegram_manager.services.telegram_client import save_session_file
        session_file_path = await save_session_file(session_file, phone_number)

    from telegram_manager.services.telegram_client import update_account_in_db
    updated_account = await update_account_in_db(db, phone_number, app_id, app_hash_id, session_file_path)

    return {"message": "Account updated successfully", "phone_number": updated_account.phone_number}

@router.delete("/{phone_number}")
async def delete_account(phone_number: str, db: Session = Depends(get_db)):
    from telegram_manager.services.telegram_client import delete_account_in_db
    await delete_account_in_db(db, phone_number)
    return {"message": "Account deleted successfully", "phone_number": phone_number}
