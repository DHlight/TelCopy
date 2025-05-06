from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"
    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(String, unique=True, index=True)
    api_hash = Column(String)
    phone_number = Column(String, unique=True, index=True)
    messages = relationship("Message", back_populates="account")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("telegram_accounts.id"))
    message_id = Column(String, unique=True, index=True)
    content = Column(Text)
    read = Column(Boolean, default=False)
    account = relationship("TelegramAccount", back_populates="messages")

class MessageJob(Base):
    __tablename__ = "message_jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    in_account_id = Column(Integer, ForeignKey("telegram_accounts.id"))
    out_account_id = Column(Integer, ForeignKey("telegram_accounts.id"))
    input_channel = Column(String)
    output_channel = Column(String)
