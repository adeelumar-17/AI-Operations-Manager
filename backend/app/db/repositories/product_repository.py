'''
This module defines the ProductRepository class, which provides methods for interacting with the Product model in the database. The ProductRepository class is initialized with a SQLAlchemy Session object and provides methods to retrieve a product by its ID or SKU, search products, list products with low stock, list all catalog items, and save product updates.
Classes:
    ProductRepository: A repository class for interacting with the Product model in PostgreSQL.
Methods:
    get_by_id: Retrieves a product by its UUID.
    get_by_sku: Retrieves a product by its exact SKU string (case-insensitive).
    search_by_name_or_sku: Searches for products matching a substring query in their name or SKU.
    list_all: Lists all catalog products ordered alphabetically by name.
    list_low_stock: Lists products whose stock is at or below their reorder threshold.
    save: Persists a new or modified product to the database.
'''
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.product import Product


class ProductRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, product_id: UUID) -> Product | None:
        return self.session.get(Product, product_id)

    def get_by_sku(self, sku: str) -> Product | None:
        statement = select(Product).where(Product.sku.ilike(sku.strip()))
        return self.session.scalars(statement).first()

    def search_by_name_or_sku(self, query: str) -> list[Product]:
        from sqlalchemy import or_, and_

        q = query.strip()
        if not q:
            return []

        # Exact SKU or full-string match first (fast path, most precise)
        exact = select(Product).where(
            or_(Product.sku.ilike(q), Product.name.ilike(f"%{q}%"))
        )
        results = list(self.session.scalars(exact).all())
        if results:
            return results

        # Fallback: match if every word in the query appears somewhere in the
        # product name or SKU, tolerating plural/singular and word-order differences
        # (e.g. "ergonomic chairs" matching "Ergonomic Chair")
        words = [w for w in q.split() if w]
        if not words:
            return []
        conditions = [
            or_(Product.name.ilike(f"%{w.rstrip('s')}%"), Product.sku.ilike(f"%{w}%"))
            for w in words
        ]
        statement = select(Product).where(and_(*conditions))
        return list(self.session.scalars(statement).all())

    def list_all(self) -> list[Product]:
        statement = select(Product).order_by(Product.name)
        return list(self.session.scalars(statement).all())

    def list_low_stock(self) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.stock_quantity <= Product.reorder_threshold)
            .order_by(Product.sku)
        )
        return list(self.session.scalars(statement).all())

    def save(self, product: Product) -> Product:
        self.session.add(product)
        self.session.flush()
        return product