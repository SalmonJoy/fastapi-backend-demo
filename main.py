from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from router import router


STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Simple FastAPI App")
app.include_router(router)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
