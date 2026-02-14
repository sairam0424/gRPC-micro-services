import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .models import InventoryItem, ProcessedEvent
from .bloom_filter import filter_manager

logger = logging.getLogger(__name__)

async def check_and_record_event(db: AsyncSession, event_id: str, service: str) -> bool:
    """Check if event was processed, if not record it. Returns True if new, False if duplicate."""
    result = await db.execute(
        select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
    )
    if result.scalar():
        return False
    
    db.add(ProcessedEvent(event_id=event_id, service=service))
    # We don't commit here, caller should commit as part of the transaction
    return True

async def get_inventory_item(db: AsyncSession, product_id: str):
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.product_id == product_id)
    )
    return result.scalar()

async def get_all_inventory(db: AsyncSession):
    result = await db.execute(select(InventoryItem))
    return result.scalars().all()

async def reserve_stock_atomic(db: AsyncSession, order_id: str, items: list):
    """
    Atomically reserve stock for multiple items.
    Locks the rows using SELECT FOR UPDATE.
    """
    logger.info(f"Attempting atomic reservation for order {order_id}")
    items_to_reserve = []
    
    for item_req in items:
        # with_for_update() ensures we lock the rows until the transaction ends
        result = await db.execute(
            select(InventoryItem)
            .where(InventoryItem.product_id == item_req.product_id)
            .with_for_update()
        )
        db_item = result.scalar()
        
        if not db_item:
            return False, f"Product {item_req.product_id} not found"
        
        if db_item.quantity < item_req.quantity:
            return False, f"Insufficient stock for {item_req.product_id}"
            
        items_to_reserve.append((db_item, item_req.quantity))
    
    # All items are available and locked, proceed to deduct
    for db_item, qty in items_to_reserve:
        db_item.quantity -= qty
        if db_item.quantity == 0:
            filter_manager.update_stock_status(db_item.product_id, False)
        
    await db.commit()
    return True, "Stock reserved successfully", items_to_reserve

async def release_stock_atomic(db: AsyncSession, order_id: str, items: list):
    """Restore stock levels."""
    for item_req in items:
        await db.execute(
            update(InventoryItem)
            .where(InventoryItem.product_id == item_req.product_id)
            .values(quantity=InventoryItem.quantity + item_req.quantity)
        )
        # Re-enable in-stock filter
        filter_manager.update_stock_status(item_req.product_id, True)
    await db.commit()
    return True

async def update_stock_level(db: AsyncSession, product_id: str, change: int, override_quantity: int = None):
    """Update or create a product stock level. If override_quantity is provided, it sets the value directly."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.product_id == product_id).with_for_update()
    )
    db_item = result.scalar()
    
    if not db_item:
        new_qty = override_quantity if override_quantity is not None else max(0, change)
        db_item = InventoryItem(
            product_id=product_id,
            name=f"Product {product_id}",
            quantity=new_qty
        )
        db.add(db_item)
        # Add to catalog and update stock status
        filter_manager.add_to_catalog(product_id)
        filter_manager.update_stock_status(product_id, db_item.quantity > 0)
    else:
        if override_quantity is not None:
            db_item.quantity = override_quantity
        else:
            db_item.quantity = max(0, db_item.quantity + change)
        filter_manager.update_stock_status(product_id, db_item.quantity > 0)
        
    await db.commit()
    return db_item
