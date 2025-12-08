from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.webhook import router as webhook_router
from app.routers.bus_location import router as bus_location_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(bus_location_router)
