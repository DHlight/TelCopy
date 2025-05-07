from telegram_manager.db.base import Base
from telegram_manager.db.session import engine
from telegram_manager.db import models

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    init_db()
