import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from app.cache import CacheManager
from app.main import InventoryServicer
from inventory.v1 import inventory_pb2

class TestCaching(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Mock Redis Client
        self.mock_redis = MagicMock()
        patcher = patch('redis.Redis', return_value=self.mock_redis)
        self.addCleanup(patcher.stop)
        patcher.start()
        
        self.cache_manager = CacheManager()
        self.servicer = InventoryServicer()

    @patch('app.main.cache_manager')
    @patch('app.main.crud.get_inventory_item', new_callable=AsyncMock)
    @patch('app.main.writer_session')
    async def test_check_stock_cache_hit(self, mock_session, mock_get_item, mock_cache):
        # Setup: Cache hit
        mock_cache.get_stock.return_value = 10
        
        request = inventory_pb2.CheckStockRequest(product_id="PROD-001")
        response = await self.servicer.CheckStock(request, None)
        
        self.assertEqual(response.quantity, 10)
        mock_cache.get_stock.assert_called_with("PROD-001")
        mock_get_item.assert_not_called()

    @patch('app.main.cache_manager')
    @patch('app.main.crud.get_inventory_item', new_callable=AsyncMock)
    @patch('app.main.writer_session')
    async def test_check_stock_cache_miss(self, mock_session, mock_get_item, mock_cache):
        # Setup: Cache miss
        mock_cache.get_stock.side_effect = [None, None] # First miss, second re-check also miss
        mock_get_item.return_value = MagicMock(quantity=20)
        
        # Single flight context manager needs to be mocked
        mock_cache.single_flight = MagicMock()
        mock_cache.single_flight.return_value.__aenter__ = AsyncMock()
        mock_cache.single_flight.return_value.__aexit__ = AsyncMock()

        request = inventory_pb2.CheckStockRequest(product_id="PROD-001")
        response = await self.servicer.CheckStock(request, None)
        
        self.assertEqual(response.quantity, 20)
        self.assertEqual(mock_cache.get_stock.call_count, 2)
        mock_get_item.assert_called_once()
        mock_cache.set_stock.assert_called_with("PROD-001", 20)

    @patch('app.main.cache_manager')
    @patch('app.main.filter_manager')
    @patch('app.main.crud.reserve_stock_atomic', new_callable=AsyncMock)
    @patch('app.main.writer_session')
    async def test_reserve_stock_cache_reject(self, mock_session, mock_reserve, mock_filter, mock_cache):
        # Setup: Bloom filter pass, but cache rejects
        mock_filter.is_in_stock.return_value = True
        mock_cache.get_stock.return_value = 5 # only 5 in cache
        
        # Request 10
        item = inventory_pb2.InventoryItem(product_id="PROD-001", quantity=10)
        request = inventory_pb2.ReserveStockRequest(order_id="ORD-1", items=[item])
        
        response = await self.servicer.ReserveStock(request, None)
        
        self.assertFalse(response.success)
        self.assertIn("Insufficient stock", response.message)
        mock_reserve.assert_not_called()

if __name__ == '__main__':
    unittest.main()
