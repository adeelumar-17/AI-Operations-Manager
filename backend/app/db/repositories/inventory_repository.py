'''
This module defines the InventoryRepository class, which provides methods for interacting with the Inventory model in the database. The InventoryRepository class is initialized with a SQLAlchemy Session object and provides a method to record changes in inventory, including product ID, change quantity, reason for the change, resulting balance, and optional reference type and ID.
Classes:
    InventoryRepository: A class for interacting with the Inventory model in the database.
Methods:
    record_change: Records a change in inventory for a specific product, including the change quantity, reason for the change, resulting balance, and optional reference type and ID.
'''
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models.inventory import Inventory


class InventoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def record_change(
        self,
        product_id: UUID,
        change_quantity: int,
        reason: str,
        resulting_balance: int,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> Inventory:
        change = Inventory(
            product_id=product_id,
            change_quantity=change_quantity,
            reason=reason,
            resulting_balance=resulting_balance,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        self.session.add(change)
        self.session.flush()
        return change