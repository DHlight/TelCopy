import sys
sys.dont_write_bytecode = True

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from telegram_manager.routers import telegram_account_manager, telegram_job_manager
from telegram_manager.services.job_runner import load_and_schedule_jobs_on_startup
from telegram_manager.db.init_db import init_db

app = FastAPI(title="Telegram Manager API")

app.include_router(telegram_account_manager.router, prefix="/account", tags=["Telegram Account Manager"])
app.include_router(telegram_job_manager.router, prefix="/job", tags=["Telegram Job Manager"])

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(index_path)

@app.get("/index.html")
async def index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(index_path)

@app.get("/dashboard")
async def dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    return FileResponse(dashboard_path)

@app.get("/dashboard.html")
async def dashboard_html():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    return FileResponse(dashboard_path)

@app.get("/account.html")
async def account_html():
    account_path = os.path.join(os.path.dirname(__file__), "static", "account.html")
    return FileResponse(account_path)

@app.get("/task.html")
async def task_html():
    task_path = os.path.join(os.path.dirname(__file__), "static", "task.html")
    return FileResponse(task_path)

import asyncio

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(load_and_schedule_jobs_on_startup())

@app.on_event("shutdown")
async def shutdown_event():
    pass
