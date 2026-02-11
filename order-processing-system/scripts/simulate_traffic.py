import urllib.request
import urllib.parse
import json
import time
import concurrent.futures
import threading
import sys
import argparse

GATEWAY_URL = "http://127.0.0.1:8100"

class Stats:
    def __init__(self):
        self.success = 0
        self.rate_limited = 0
        self.load_shed = 0
        self.errors = 0
        self.lock = threading.Lock()

    def add(self, status):
        with self.lock:
            if status == 200:
                self.success += 1
            elif status == 429:
                self.rate_limited += 1
            elif status == 503:
                self.load_shed += 1
            else:
                self.errors += 1

    def __str__(self):
        return f"✅ SUCCESS: {self.success} | ⚠️ RATE LIMIT (429): {self.rate_limited} | 🛑 LOAD SHED (503): {self.load_shed} | ❌ ERRORS: {self.errors}"

stats = Stats()

def make_request(path="/"):
    url = f"{GATEWAY_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            stats.add(response.getcode())
    except urllib.error.HTTPError as e:
        stats.add(e.code)
    except Exception:
        stats.add(0)

def set_stress(level):
    print(f"\n[CONTROL] Setting system stress level to: {level}")
    url = f"{GATEWAY_URL}/metrics/stress?level={level}"
    try:
        req = urllib.request.Request(url, method="POST")
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Failed to set stress level: {e}")

def run_simulation(requests_count, concurrency, endpoint):
    print(f"Starting Simulation: {requests_count} requests to {endpoint} with concurrency {concurrency}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, endpoint) for _ in range(requests_count)]
        
        # Print stats every 1 second
        for _ in range(int(requests_count / concurrency) + 1):
            if all(f.done() for f in futures):
                break
            time.sleep(1)
            print(f"\r{stats}", end="", flush=True)
            
    print(f"\nSimulation Complete: {stats}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot Simulation Script for Resilience Testing")
    parser.add_argument("--requests", type=int, default=200, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=20, help="Number of concurrent threads")
    parser.add_argument("--endpoint", type=str, default="/", help="Endpoint to target")
    parser.add_argument("--stress", type=float, help="Set stress level (0.0 to 1.0) before starting")
    
    args = parser.parse_args()
    
    if args.stress is not None:
        set_stress(args.stress)
        
    try:
        run_simulation(args.requests, args.concurrency, args.endpoint)
    finally:
        if args.stress is not None:
            # Reset stress after simulation
            set_stress(0.0)
