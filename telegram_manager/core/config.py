import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./telegram_accounts.db")
    PROXY: str = os.getenv("PROXY", None)  # Proxy URL or None if not set

settings = Settings()
