from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from aiokafka import AIOKafkaConsumer
import os
import json
import asyncio
import logging

app = FastAPI(title="Kafka DLQ UI")
templates = Jinja2Templates(directory="templates")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
DLQ_TOPICS = ["inventory.dlq", "order-streamer.dlq", "analytics.dlq"]

logger = logging.getLogger("dlq-ui")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "topics": DLQ_TOPICS})

import httpx

REPLAY_SERVICE_URL = os.getenv("REPLAY_SERVICE_URL", "http://replay-service:8000")

@app.post("/api/replay/{topic}")
async def trigger_replay(topic: str):
    if topic not in DLQ_TOPICS:
        return {"error": "Invalid topic"}
    
    # Map DLQ topics to their original target topics
    target_mapping = {
        "inventory.dlq": "order-events",
        "order-streamer.dlq": "order-events",
        "analytics.dlq": "order-events" # Adjust based on actual flow
    }
    
    target = target_mapping.get(topic)
    if not target:
        return {"error": "No target topic mapping found for " + topic}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{REPLAY_SERVICE_URL}/api/replay",
                json={
                    "source": topic,
                    "target": target
                },
                timeout=30.0
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to trigger replay: {e}")
            return {"status": "error", "message": str(e)}

@app.get("/messages/{topic}")
async def get_messages(topic: str):
    if topic not in DLQ_TOPICS:
        return {"error": "Invalid topic"}
    
    messages = []
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKERS,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        group_id=f"dlq-ui-viewer-{topic}"
    )
    
    await consumer.start()
    try:
        # Fetch a batch of messages
        data = await consumer.getmany(timeout_ms=1000, max_records=50)
        for tp, msgs in data.items():
            for msg in msgs:
                try:
                    val = json.loads(msg.value.decode('utf-8'))
                    messages.append({
                        "offset": msg.offset,
                        "timestamp": msg.timestamp,
                        "content": val
                    })
                except Exception as e:
                    messages.append({
                        "offset": msg.offset,
                        "timestamp": msg.timestamp,
                        "content": msg.value.decode('utf-8', errors='replace'),
                        "error": str(e)
                    })
    finally:
        await consumer.stop()
    
    return {"messages": sorted(messages, key=lambda x: x['offset'], reverse=True)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
