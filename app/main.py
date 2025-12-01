from fastapi import FastAPI
from app.routers.webhook import router as webhook_router

app = FastAPI()

app.include_router(webhook_router)
