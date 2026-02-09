#!/bin/bash
# scripts/seed_data.sh - Generates traffic for observability demonstration

BASE_URL="http://localhost/api"
echo "--- Seeding Data for Observability Stack ---"

# 1. Signup
echo "Creating test user..."
curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "seeduser",
    "email": "seed@example.com",
    "password": "password123",
    "full_name": "Seed Data User"
  }' > /dev/null

# 2. Login to get token
echo "Logging in..."
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "seeduser",
    "password": "password123"
  }' | jq -r .access_token)

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "Failed to get token! Ensure the services are running."
  exit 1
fi

PRODUCTS=("PROD-001" "PROD-002" "PROD-003" "PROD-004" "PROD-005")
echo "Generating orders..."

for i in {1..10}
do
  PRODUCT=${PRODUCTS[$(( RANDOM % ${#PRODUCTS[@]} ))]}
  QTY=$(( (RANDOM % 5) + 1 ))
  PRICE=$(( (RANDOM % 1000) + 500 )).0
  
  echo "[$i/10] Creating order for $PRODUCT (Qty: $QTY)..."
  curl -s -X POST "$BASE_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{
      \"customer_id\": \"seeduser\",
      \"items\": [
        {\"product_id\": \"$PRODUCT\", \"quantity\": $QTY, \"price\": $PRICE}
      ]
    }" | jq -c .
  
  # Add some random latency to spread out traces
  sleep $(( (RANDOM % 2) + 1 ))
done

echo -e "\n--- Seeding Complete! ---"
echo "You can now view traces in Jaeger and metrics in Prometheus/Grafana."
