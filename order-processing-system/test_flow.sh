#!/bin/bash
# Test Script for Authentication and Order Flow

echo "--- 1. Testing Signup ---"
curl -s -X POST http://localhost/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }' | jq .

echo -e "\n--- 2. Testing Login ---"
TOKEN_RESPONSE=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }')
echo $TOKEN_RESPONSE | jq .
TOKEN=$(echo $TOKEN_RESPONSE | jq -r .access_token)

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "Failed to get token!"
  exit 1
fi

echo -e "\n--- 3. Testing Authenticated Profile (/me) ---"
curl -s http://localhost/api/me \
  -H "Authorization: Bearer $TOKEN" | jq .

echo -e "\n--- 4. Testing Create Order ---"
curl -s -X POST http://localhost/api/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "customer_id": "testuser",
    "items": [
      {"product_id": "PROD-001", "quantity": 1, "price": 1200.0}
    ]
  }' | jq .

echo -e "\n--- 5. Testing List Orders ---"
curl -s http://localhost/api/orders \
  -H "Authorization: Bearer $TOKEN" | jq .
