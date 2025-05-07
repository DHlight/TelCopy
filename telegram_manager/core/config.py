import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./telegram_accounts.db")

settings = Settings()
