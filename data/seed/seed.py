"""Database seed script for realistic OfficeHub enterprise data (Module 1).

Seeds:
- System users (manager)
- Customers (Ahmed Industries, Beta Corp, Delta Logistics)
- Products with stock_quantity and categories
- Quotes and quote line items
- Orders (ORD-5001) and order line items
- Invoices (overdue invoice INV-2024-001)

Usage:
    python -m data.seed.seed
"""

import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.db.database import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.customer import Customer
from backend.app.db.models.product import Product
from backend.app.db.models.quote import Quote
from backend.app.db.models.quote_item import QuoteItem
from backend.app.db.models.order import Order
from backend.app.db.models.order_item import OrderItem
from backend.app.db.models.invoice import Invoice


def seed_database():
    print("=" * 60)
    print("Seeding OfficeHub Domain Database")
    print("=" * 60)

    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        today = date.today()

        # 1. Users
        manager_user = db.query(User).filter(User.email == "manager@officehub.com").first()
        if not manager_user:
            manager_user = User(
                id=uuid4(),
                email="manager@officehub.com",
                hashed_password="pbkdf2:sha256:fakehashformanager",
                full_name="Operations Manager",
                role="manager",
                is_active=True,
                created_at=now,
            )
            db.add(manager_user)
            db.commit()
            print("✓ Created manager user account.")

        # 2. Customers
        cust_ahmed = db.query(Customer).filter(Customer.name == "Ahmed Industries").first()
        if not cust_ahmed:
            cust_ahmed = Customer(
                id=uuid4(),
                name="Ahmed Industries",
                email="purchasing@ahmed-ind.com",
                phone="+1-555-0199",
                company_name="Ahmed Industries LLC",
                notes="Preferred customer tier - approved for up to 15% discount.",
                created_at=now - timedelta(days=180),
            )
            db.add(cust_ahmed)

        cust_beta = db.query(Customer).filter(Customer.name == "Beta Corp").first()
        if not cust_beta:
            cust_beta = Customer(
                id=uuid4(),
                name="Beta Corp",
                email="ops@betacorp.io",
                phone="+1-555-0244",
                company_name="Beta Corporation",
                notes="Regular customer tier - max 10% discount.",
                created_at=now - timedelta(days=90),
            )
            db.add(cust_beta)

        cust_delta = db.query(Customer).filter(Customer.name == "Delta Logistics").first()
        if not cust_delta:
            cust_delta = Customer(
                id=uuid4(),
                name="Delta Logistics",
                email="procurement@deltalogistics.com",
                phone="+1-555-0377",
                company_name="Delta Logistics Inc.",
                notes="Regular customer tier.",
                created_at=now - timedelta(days=45),
            )
            db.add(cust_delta)

        db.commit()
        print("✓ Verified customer accounts (Ahmed Industries, Beta Corp, Delta Logistics).")

        # 3. Products
        p_chair = db.query(Product).filter(Product.sku == "SKU-1234").first()
        if not p_chair:
            products_data = [
                ("SKU-1234", "Ergonomic Mesh Office Chair", "High-comfort task chair with lumbar support", "Furniture", Decimal("249.99"), 150, 20),
                ("SKU-5001", "Standard A4 Copy Paper (Box of 5)", "Premium 80gsm white printer paper", "Office Supplies", Decimal("34.50"), 500, 50),
                ("SKU-9999", "Executive Walnut Standing Desk", "Motorized dual-motor adjustable sit-stand desk", "Furniture", Decimal("699.00"), 15, 5),
                ("SKU-2001", "Wireless Ergonomic Mouse", "Rechargeable silent click 2.4G optical mouse", "Electronics", Decimal("29.99"), 220, 30),
                ("SKU-3001", "34-Inch UltraWide Curved Monitor", "144Hz IPS productivity display with USB-C hub", "Electronics", Decimal("499.00"), 40, 10),
                ("SKU-4001", "Noise-Cancelling Office Headset", "Bluetooth wireless headset with boom mic", "Electronics", Decimal("89.99"), 90, 15),
            ]
            for sku, name, desc, category, price, qty, reorder in products_data:
                p = Product(
                    id=uuid4(),
                    sku=sku,
                    name=name,
                    description=desc,
                    category=category,
                    unit_price=price,
                    stock_quantity=qty,
                    reorder_threshold=reorder,
                    active=True,
                    created_at=now,
                )
                db.add(p)
            db.commit()
            print("✓ Created catalog products with inventory levels.")

        p_chair = db.query(Product).filter(Product.sku == "SKU-1234").first()
        p_paper = db.query(Product).filter(Product.sku == "SKU-5001").first()

        # 4. Quotes
        quote_1 = db.query(Quote).filter(Quote.quote_number == "QUO-1001").first()
        if not quote_1:
            quote_1 = Quote(
                id=uuid4(),
                quote_number="QUO-1001",
                customer_id=cust_ahmed.id,
                status="draft",
                subtotal=Decimal("3450.00"),
                discount_percent=Decimal("10.0"),
                discount_amount=Decimal("345.00"),
                total=Decimal("3105.00"),
                created_at=now - timedelta(days=3),
            )
            db.add(quote_1)
            db.flush()

            q_item = QuoteItem(
                id=uuid4(),
                quote_id=quote_1.id,
                product_id=p_paper.id,
                quantity=100,
                unit_price=p_paper.unit_price,
                line_total=Decimal("3450.00"),
            )
            db.add(q_item)
            db.commit()
            print("✓ Created sample quote QUO-1001.")

        # 5. Orders & Invoices
        order_1 = db.query(Order).filter(Order.order_number == "ORD-5001").first()
        if not order_1:
            order_1 = Order(
                id=uuid4(),
                order_number="ORD-5001",
                customer_id=cust_ahmed.id,
                status="shipped",
                subtotal=Decimal("1249.95"),
                total=Decimal("1249.95"),
                created_at=now - timedelta(days=10),
            )
            db.add(order_1)
            db.flush()

            ord_item = OrderItem(
                id=uuid4(),
                order_id=order_1.id,
                product_id=p_chair.id,
                quantity=5,
                unit_price=p_chair.unit_price,
                line_total=Decimal("1249.95"),
            )
            db.add(ord_item)
            db.commit()
            print("✓ Created sample order ORD-5001.")

        # Overdue invoice for Beta Corp
        inv_overdue = db.query(Invoice).filter(Invoice.invoice_id == "INV-2024-001").first()
        if not inv_overdue:
            inv_overdue = Invoice(
                id=uuid4(),
                invoice_id="INV-2024-001",
                customer_id=cust_beta.id,
                order_id=None,
                amount=Decimal("850.00"),
                issue_date=today - timedelta(days=50),
                due_date=today - timedelta(days=20),
                status="overdue",
                created_at=now - timedelta(days=50),
            )
            db.add(inv_overdue)
            db.commit()
            print("✓ Created overdue invoice INV-2024-001.")

        print("=" * 60)
        print("DATABASE SEEDING COMPLETED SUCCESSFULLY!")
        print("=" * 60)


if __name__ == "__main__":
    seed_database()
