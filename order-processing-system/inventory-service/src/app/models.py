from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from .database import Base

class InventoryItem(Base):
    __tablename__ = "inventory"

    product_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), on_server_default=func.now(), on_update=func.now())

    def __repr__(self):
        return f"<InventoryItem(product_id='{self.product_id}', name='{self.name}', quantity={self.quantity})>"
