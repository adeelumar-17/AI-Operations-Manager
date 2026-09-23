"""Create fresh, disposable fixtures in a LOCAL PostgreSQL database only.

Usage: python -m scripts.seed_audit_verification > audit-fixtures.json
Never deletes or updates existing business records. IDs are new on each run.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.engine import make_url
from backend.app.core.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import User, Customer, Product, Quote, QuoteItem, Invoice, Payment, Order, OrderItem


def main():
    url = make_url(settings.DATABASE_URL)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not url.drivername.startswith("postgresql"):
        raise SystemExit("Refusing to seed: DATABASE_URL must point to local PostgreSQL (localhost/127.0.0.1/::1).")
    token = uuid4().hex[:8]
    result = {}
    with SessionLocal() as db:
        for role in ("manager", "staff"):
            row = User(id=uuid4(), email=f"audit-{role}-{token}@example.invalid", full_name=f"Audit {role}",
                       role=role, is_active=True, hashed_password="demo-header-identity-no-login")
            db.add(row)
            result[role + "_id"] = str(row.id)
        customer = Customer(id=uuid4(), name=f"Audit Ahmed {token}", notes="Regular customer tier.")
        preferred = Customer(id=uuid4(), name=f"Audit Preferred {token}", notes="Preferred customer tier - approved for up to 15% discount.")
        product = Product(id=uuid4(), sku=f"AUDIT-{token}", name=f"Audit Paper {token}", category="Office",
                          unit_price=100, stock_quantity=100, reorder_threshold=10)
        db.add_all([customer, preferred, product]); db.flush()
        result.update(customer_id=str(customer.id), preferred_id=str(preferred.id), product_id=str(product.id), sku=product.sku)
        for label, owner in [("quote", customer), ("reject_quote", customer), ("preferred_quote", preferred)]:
            quote = Quote(id=uuid4(), quote_number=f"AUDIT-{label}-{token}", customer_id=owner.id, status="approved",
                          subtotal=100, total=100, discount_percent=0, discount_amount=0)
            db.add(quote); db.flush()
            db.add(QuoteItem(id=uuid4(), quote_id=quote.id, product_id=product.id, quantity=1, unit_price=100, line_total=100))
            result[label + "_id"] = str(quote.id)
        invoice = Invoice(id=uuid4(), invoice_id=f"AUDIT-INV-{token}", customer_id=customer.id,
                          amount=100, status="partially_paid", issue_date=date.today()-timedelta(days=10), due_date=date.today()-timedelta(days=3))
        paid = Invoice(id=uuid4(), invoice_id=f"AUDIT-PAID-{token}", customer_id=customer.id,
                       amount=100, status="paid", issue_date=date.today()-timedelta(days=10), due_date=date.today()-timedelta(days=3), paid_date=date.today())
        order = Order(id=uuid4(), order_number=f"AUDIT-ORD-{token}", customer_id=customer.id, status="pending", subtotal=200, total=200)
        db.add_all([invoice, paid, order]); db.flush()
        db.add_all([Payment(id=uuid4(), invoice_id=invoice.id, amount=Decimal("40"), method="cash"),
                    Payment(id=uuid4(), invoice_id=paid.id, amount=Decimal("100"), method="cash"),
                    OrderItem(id=uuid4(), order_id=order.id, product_id=product.id, quantity=2, unit_price=100, line_total=200)])
        result.update(invoice_id=str(invoice.id), invoice_number=invoice.invoice_id, paid_invoice_id=str(paid.id),
                      order_id=str(order.id), order_number=order.order_number)
        db.commit()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
