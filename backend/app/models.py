from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # word ids picked as practice targets for this conversation
    target_word_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.seq"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, index=True)  # order within conversation
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    # full transparency: [{name, args, output}] for every tool call the assistant made this turn
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(10), default="word")  # word | phrase
    meaning: Mapped[str] = mapped_column(Text, default="")
    examples: Mapped[list] = mapped_column(JSON, default=list)  # 2-3 example sentences
    collocations: Mapped[list] = mapped_column(JSON, default=list)
    register_notes: Mapped[str] = mapped_column(Text, default="")  # formal/casual guidance
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_decay_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list["WordEvent"]] = relationship(back_populates="word", cascade="all, delete-orphan")


class WordEvent(Base):
    """Audit log of every score change — powers the dashboard history."""

    __tablename__ = "word_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    # perfect_unprompted | perfect_prompted | awkward | wrong | passive | decay | manual
    event_type: Mapped[str] = mapped_column(String(30))
    delta: Mapped[float] = mapped_column(Float)
    score_after: Mapped[float] = mapped_column(Float)
    judge_notes: Mapped[str] = mapped_column(Text, default="")  # feedback / suggestion from judge
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    word: Mapped[Word] = relationship(back_populates="events")
