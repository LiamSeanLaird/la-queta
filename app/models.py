from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.extensions import db


class Level(db.Model):
    __tablename__ = "levels"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lessons: Mapped[list["Lesson"]] = relationship(back_populates="level")
    decks: Mapped[list["Deck"]] = relationship(back_populates="level")


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    current_level_id: Mapped[str | None] = mapped_column(
        String(16),
        ForeignKey("levels.id"),
        nullable=True,
    )

    current_level: Mapped[Level | None] = relationship()
    lesson_progress: Mapped[list["UserLessonProgress"]] = relationship(
        back_populates="user"
    )
    card_progress: Mapped[list["UserCardProgress"]] = relationship(
        back_populates="user"
    )


class Lesson(db.Model):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    level_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("levels.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sections_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    practice_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    level: Mapped[Level] = relationship(back_populates="lessons")
    progress: Mapped[list["UserLessonProgress"]] = relationship(
        back_populates="lesson"
    )


class Deck(db.Model):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("levels.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    level: Mapped[Level] = relationship(back_populates="decks")
    cards: Mapped[list["Card"]] = relationship(back_populates="deck")


class Card(db.Model):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    catalan: Mapped[str] = mapped_column(String(200), nullable=False)
    english: Mapped[str] = mapped_column(String(200), nullable=False)
    pronunciation: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    hint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pos: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    plural: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    forms_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    grammar_lesson_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("lessons.id"),
        nullable=True,
    )

    deck: Mapped[Deck] = relationship(back_populates="cards")
    grammar_lesson: Mapped[Lesson | None] = relationship()
    progress: Mapped[list["UserCardProgress"]] = relationship(back_populates="card")


class UserLessonProgress(db.Model):
    __tablename__ = "user_lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("lessons.id"), nullable=False
    )
    completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    exercises_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exercises_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="lesson_progress")
    lesson: Mapped[Lesson] = relationship(back_populates="progress")


class UserCardProgress(db.Model):
    __tablename__ = "user_card_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False)
    seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[User] = relationship(back_populates="card_progress")
    card: Mapped[Card] = relationship(back_populates="progress")
