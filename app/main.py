from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Nolga Backend", lifespan=lifespan)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}