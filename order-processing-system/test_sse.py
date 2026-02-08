import requests

def test_sse():
    url = "http://localhost/api/orders/events"
    print(f"Connecting to {url}...")
    try:
        response = requests.get(url, stream=True, timeout=15)
        print("Connected. Waiting for events...")
        for line in response.iter_lines():
            if line:
                print(f"Received: {line.decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_sse()
