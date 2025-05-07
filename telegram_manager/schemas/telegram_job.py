from pydantic import BaseModel

class JobCreate(BaseModel):
    source_account_id: str
    source_channel: int
    dest_account_id: str
    dest_channel: int
    job_type: int  # Changed to int to represent enum values

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
