from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from telegram_manager.db.base import Base
import enum

class JobTypeEnum(enum.IntEnum):
    full = 0
    readtime = 1
    clean = 2

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
    bot_token = Column(String, nullable=True)  # New field for bot token

class TelegramJob(Base):
    __tablename__ = "telegram_jobs"

    id = Column(String, primary_key=True, index=True)  # Changed from Integer to String for hash id
    source_account_id = Column(String, ForeignKey("telegram_accounts.phone_number"), nullable=False)
    source_channel = Column(Integer, nullable=False)
    dest_account_id = Column(String, ForeignKey("telegram_accounts.phone_number"), nullable=False)
    dest_channel = Column(Integer, nullable=False)
    job_type = Column(Integer, nullable=False)  # Changed to Integer to use enum values
    status = Column(Integer, default=JobStatusEnum.pending.value)  # Changed to Integer with default enum value
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    filter_user_id = Column(String, nullable=True)

    messages = relationship("TelegramMessage", back_populates="job")

    @property
    def status_int(self) -> int:
        # Return status as int, converting if necessary
        if isinstance(self.status, int):
            return self.status
        try:
            return int(self.status)
        except Exception:
            return JobStatusEnum.pending.value

class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("telegram_jobs.id"), nullable=False)  # Changed to String to match TelegramJob.id
    message_id = Column(String, nullable=False)
    privateid = Column(String, nullable=True, index=True)  # New field for privateid as combination of message_id and job_id
    sender = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=True)
    tracking = Column(Integer, default=0, nullable=False)
    media_path = Column(String, nullable=True)

    job = relationship("TelegramJob", back_populates="messages")
