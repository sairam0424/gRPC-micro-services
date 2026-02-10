import asyncio
import grpc
import sys
import os

# Add generated to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "generated")))

from inventory.v1 import inventory_pb2, inventory_pb2_grpc

async def run_test():
    async with grpc.aio.insecure_channel('localhost:50052') as channel:
        stub = inventory_pb2_grpc.InventoryServiceStub(channel)
        
        product_id = "PROD-001"
        
        print(f"--- 1. First Check (Cache Miss / Coalescing) ---")
        response1 = await stub.CheckStock(inventory_pb2.CheckStockRequest(product_id=product_id))
        print(f"Response 1: {response1.product_id} = {response1.quantity}")
        
        print(f"\n--- 2. Second Check (Should be Cache Hit) ---")
        response2 = await stub.CheckStock(inventory_pb2.CheckStockRequest(product_id=product_id))
        print(f"Response 2: {response2.product_id} = {response2.quantity}")
        
        print(f"\n--- 3. Updating Stock (Should Invalidate Cache) ---")
        update_resp = await stub.UpdateStock(inventory_pb2.UpdateStockRequest(product_id=product_id, quantity_change=5))
        print(f"Update Response: New Quantity = {update_resp.new_quantity}")
        
        print(f"\n--- 4. Third Check (Should be Cache Miss then populate) ---")
        response3 = await stub.CheckStock(inventory_pb2.CheckStockRequest(product_id=product_id))
        print(f"Response 3: {response3.product_id} = {response3.quantity}")

if __name__ == "__main__":
    asyncio.run(run_test())
