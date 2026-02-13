import duckdb
import os
import pandas as pd
from datetime import datetime

class MLFeatureStore:
    def __init__(self, db_path='analytics-pipeline/src/features.duckdb'):
        self.db_path = db_path
        self.conn = duckdb.connect(database=self.db_path, read_only=False)
        self._setup_schema()

    def _setup_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_features (
                customer_id VARCHAR PRIMARY KEY,
                total_orders INTEGER,
                last_order_time TIMESTAMP,
                avg_order_value DOUBLE
            )
        """)

    def update_features(self, customer_id, order_count, last_time):
        self.conn.execute("""
            INSERT INTO customer_features (customer_id, total_orders, last_order_time)
            VALUES (?, ?, ?)
            ON CONFLICT (customer_id) DO UPDATE SET
                total_orders = excluded.total_orders,
                last_order_time = excluded.last_order_time
        """, (customer_id, order_count, last_time))
        print(f"Features updated for {customer_id}")

    def get_features(self, customer_id):
        return self.conn.execute("SELECT * FROM customer_features WHERE customer_id = ?", (customer_id,)).df()

if __name__ == "__main__":
    # Example usage for manual verification
    store = MLFeatureStore()
    store.update_features("CUST-001", 5, datetime.now())
    print(store.get_features("CUST-001"))
