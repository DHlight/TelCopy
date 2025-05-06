from pydantic import BaseModel

class TelegramAccountBase(BaseModel):
    api_id: str
    api_hash: str
    phone_number: str

class TelegramAccountCreate(TelegramAccountBase):
    pass

class TelegramAccount(TelegramAccountBase):
    id: int

    class Config:
        orm_mode = True

class MessageBase(BaseModel):
    content: str
    read: bool = False

class MessageCreate(MessageBase):
    account_id: int
    message_id: str

class Message(MessageBase):
    id: int
    account_id: int

    class Config:
        orm_mode = True
