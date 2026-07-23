"""CLI: poetry run python scripts/seed.py"""

from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models import Card, Deck, Lesson, Level
from app.services.seed import seed_all


def main() -> None:
    application = create_app()
    with application.app_context():
        seed_all()
        codes = db.session.scalars(select(Level.code).order_by(Level.sort_order)).all()
        lesson_count = db.session.scalar(select(func.count()).select_from(Lesson)) or 0
        deck_count = db.session.scalar(select(func.count()).select_from(Deck)) or 0
        card_count = db.session.scalar(select(func.count()).select_from(Card)) or 0
        print(f"Seeded levels: {', '.join(codes)}")
        print(f"Seeded lessons: {lesson_count}")
        print(f"Seeded decks: {deck_count} ({card_count} cards)")


if __name__ == "__main__":
    main()
