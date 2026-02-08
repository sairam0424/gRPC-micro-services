import requests
import json
import threading
import time

def listen_sse():
    print("Connecting to SSE stream...")
    try:
        response = requests.get("http://localhost:8000/api/orders/events", stream=True, timeout=30)
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data = json.loads(decoded_line[6:])
                    print(f"\n[SSE Event] Order {data['order_id']} Status: {data['status']}")
                    if 'items' in data:
                        print(f"  Items: {data['items']}")
                    else:
                        print("  WARNING: Missing items in event data!")
    except Exception as e:
        print(f"SSE Listener stopped: {e}")

def create_order():
    time.sleep(2) # Wait for listener to connect
    print("Creating test order...")
    url = "http://localhost:8000/api/orders"
    payload = {
        "customer_id": "TEST-USER-1",
        "items": [
            {
                "product_id": "PROD-001",
                "quantity": 5,
                "price": 1500.0
            }
        ]
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Order created: {response.json()}")
        else:
            print(f"Failed to create order: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error creating order: {e}")

if __name__ == "__main__":
    listener_thread = threading.Thread(target=listen_sse, daemon=True)
    listener_thread.start()
    
    create_order()
    
    # Wait for status updates (PENDING -> COMPLETED)
    print("\nWaiting for real-time updates (8 seconds)...")
    time.sleep(8)
    print("Verification complete.")
