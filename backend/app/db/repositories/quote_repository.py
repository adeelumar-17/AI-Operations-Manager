'''
This module defines the QuoteRepository class, which provides methods for interacting with the Quote model in the database. The QuoteRepository class is initialized with a SQLAlchemy Session object and provides methods to retrieve a quote by its ID, get a quote with its items, add an item to a quote, update an item in a quote, delete an item from a quote, and save a quote to the database.
Classes:
    QuoteRepository: A class for interacting with the Quote model in the database.
Methods:
    get_by_id: Retrieves a quote by its ID.
    get_with_items: Gets a quote with its items.
    add_item: Adds an item to a quote.
    update_item: Updates an item in a quote.
    delete_item: Deletes an item from a quote.
    save: Saves a quote to the database.
'''
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models.quote import Quote
from backend.app.db.models.quote_item import QuoteItem


class QuoteRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, quote_id: UUID) -> Quote | None:
        return self.session.get(Quote, quote_id)

    def list_all(self, status: str | None = None) -> list[Quote]:
        statement = select(Quote).options(selectinload(Quote.items)).order_by(Quote.created_at.desc())
        if status and status != "all":
            statement = statement.where(Quote.status == status)
        return list(self.session.scalars(statement).all())

    def get_with_items(self, quote_id: UUID) -> Quote | None:
        statement = (
            select(Quote)
            .where(Quote.id == quote_id)
            .options(selectinload(Quote.items))
        )
        return self.session.scalars(statement).one_or_none()

    def add_item(self, item: QuoteItem) -> QuoteItem:
        self.session.add(item)
        self.session.flush()
        return item

    def update_item(self, item: QuoteItem) -> QuoteItem:
        self.session.add(item)
        self.session.flush()
        return item

    def delete_item(self, item: QuoteItem) -> None:
        self.session.delete(item)
        self.session.flush()

    def save(self, quote: Quote) -> Quote:
        self.session.add(quote)
        self.session.flush()
        return quote
