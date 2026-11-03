from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_keys, auth, works
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Nolga Backend", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(works.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}