from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from telegram_manager.db.base import Base
import enum

class JobTypeEnum(enum.IntEnum):
    full = 0
    readtime = 1

class JobStatusEnum(enum.IntEnum):
    pending = 0
    running = 1
    completed = 2
    failed = 3
    stopped = 4

class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    phone_number = Column(String, primary_key=True, index=True)
    app_id = Column(Integer, nullable=False)
    app_hash_id = Column(String, nullable=False)
    session_file_path = Column(String, nullable=False)

class TelegramJob(Base):
    __tablename__ = "telegram_jobs"

    id = Column(Integer, primary_key=True, index=True)
    source_account_id = Column(String, ForeignKey("telegram_accounts.phone_number"), nullable=False)
    source_channel = Column(Integer, nullable=False)
    dest_account_id = Column(String, ForeignKey("telegram_accounts.phone_number"), nullable=False)
    dest_channel = Column(Integer, nullable=False)
    job_type = Column(Integer, nullable=False)  # Changed to Integer to use enum values
    status = Column(Integer, default=JobStatusEnum.pending.value)  # Changed to Integer with default enum value
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("TelegramMessage", back_populates="job")

class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("telegram_jobs.id"), nullable=False)
    message_id = Column(String, nullable=False)
    sender = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=True)

    job = relationship("TelegramJob", back_populates="messages")
