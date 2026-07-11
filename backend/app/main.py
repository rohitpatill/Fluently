from dotenv import load_dotenv

load_dotenv()  # must run before anything reads provider env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import chat, conversations, dashboard, memory, words
from .services import memory_service

app = FastAPI(title="ENG — English Proficiency Companion", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(words.router)
app.include_router(memory.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    memory_service.ensure_files()


@app.get("/api/health")
def health():
    return {"status": "ok"}
