from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import models, database
from app.telegram.client import TelegramAccountManager
from app.schemas import schemas
import asyncio

router = APIRouter()

account_manager = TelegramAccountManager()

async def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.TelegramAccount)
def create_account(account: schemas.TelegramAccountCreate, db: Session = Depends(get_db)):
    db_account = db.query(models.TelegramAccount).filter(models.TelegramAccount.phone_number == account.phone_number).first()
    if db_account:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    new_account = models.TelegramAccount(
        api_id=account.api_id,
        api_hash=account.api_hash,
        phone_number=account.phone_number
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    # Start Telegram client for new account
    asyncio.create_task(account_manager.start_client(new_account))
    return new_account

@router.put("/{account_id}", response_model=schemas.TelegramAccount)
def update_account(account_id: int, account: schemas.TelegramAccountCreate, db: Session = Depends(get_db)):
    db_account = db.query(models.TelegramAccount).filter(models.TelegramAccount.id == account_id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")
    db_account.api_id = account.api_id
    db_account.api_hash = account.api_hash
    db_account.phone_number = account.phone_number
    db.commit()
    db.refresh(db_account)
    # Restart Telegram client for updated account
    asyncio.create_task(account_manager.stop_client(account_id))
    asyncio.create_task(account_manager.start_client(db_account))
    return db_account

@router.get("/", response_model=list[schemas.TelegramAccount])
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(models.TelegramAccount).all()
    return accounts
