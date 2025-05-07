from pydantic import BaseModel
from typing import Optional

class JobCreate(BaseModel):
    source_account_id: str
    source_channel: int
    dest_account_id: str
    dest_channel: int
    job_type: int  # Changed to int to represent enum values
    filter_user_id: Optional[str] = None

class JobResponse(BaseModel):
    id: int
    source_account_id: str
    source_channel: int
    dest_account_id: str
    dest_channel: int
    job_type: int  # Changed to int
    status: int  # Changed to int

    class Config:
        orm_mode = True
        from_attributes = True
