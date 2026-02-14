.PHONY: generate clean build-python build-go up down up-dev tidy test jaeger prometheus grafana loki kafka-ui cdc-setup restart logs seed status help

PROTOC_GEN_GO := $(shell which protoc-gen-go)
PROTOC_GEN_GO_GRPC := $(shell which protoc-gen-go-grpc)

tidy:
	@echo "Tidying Go modules..."
	cd order-service && go mod tidy
	cd order-streamer && go mod tidy

generate:
	@echo "Generating Python gRPC code..."
	mkdir -p api-gateway/src/generated
	cd api-gateway && ./venv/bin/python -m grpc_tools.protoc -I../proto -I.. \
	    --python_out=src/generated --grpc_python_out=src/generated \
	    ../proto/order/v1/order.proto ../proto/inventory/v1/inventory.proto ../proto/stream/v1/stream.proto
	touch api-gateway/src/generated/__init__.py
	find api-gateway/src/generated -type d -exec touch {}/__init__.py \;
	
	mkdir -p inventory-service/src/generated
	cd api-gateway && ./venv/bin/python -m grpc_tools.protoc -I../proto -I.. \
	    --python_out=../inventory-service/src/generated --grpc_python_out=../inventory-service/src/generated \
	    ../proto/inventory/v1/inventory.proto
	touch inventory-service/src/generated/__init__.py
	find inventory-service/src/generated -type d -exec touch {}/__init__.py \;
	
	@echo "Generating Go gRPC code..."
	mkdir -p order-service/pkg/generated
	export PATH=$$PATH:$$(go env GOPATH)/bin && \
		protoc \
		-Iproto \
		-I. \
		-I/usr/local/include \
		-I/opt/homebrew/include \
		-I$$(go env GOPATH)/pkg/mod \
		--go_out=order-service/pkg/generated --go_opt=paths=source_relative \
		--go-grpc_out=order-service/pkg/generated --go-grpc_opt=paths=source_relative \
		--grpc-gateway_out=order-service/pkg/generated --grpc-gateway_opt=paths=source_relative \
		--openapiv2_out=order-service/pkg/generated \
		proto/order/v1/order.proto proto/inventory/v1/inventory.proto proto/stream/v1/stream.proto
	
	mkdir -p order-streamer/pkg/generated
	export PATH=$$PATH:$$(go env GOPATH)/bin && \
		protoc \
		-Iproto \
		-I. \
		-I/usr/local/include \
		-I/opt/homebrew/include \
		-I$$(go env GOPATH)/pkg/mod \
		--go_out=order-streamer/pkg/generated --go_opt=paths=source_relative \
		--go-grpc_out=order-streamer/pkg/generated --go-grpc_opt=paths=source_relative \
		proto/stream/v1/stream.proto
	
	@echo "Validating OpenAPI spec with go-swagger..."
	export PATH=$$PATH:$$(go env GOPATH)/bin && \
	swagger validate order-service/pkg/generated/order/v1/order.swagger.json
	$(MAKE) tidy

clean:
	rm -rf api-gateway/src/generated/*
	rm -rf order-service/pkg/generated/*
	rm -rf order-streamer/pkg/generated/*
	rm -rf inventory-service/src/generated/*

up:
	docker compose up --build -d

up-dev:
# 	docker compose -f docker-compose.dev.yml build --parallel
# 	docker compose -f docker-compose.dev.yml up
	docker compose -f docker-compose.dev.yml up --build

restart:
	docker compose restart

down:
	docker compose down

test:
	./test_flow.sh

test-resilience:
	@echo "Running Resilience Verification (Rate Limiting & Load Shedding)..."
	python3 verify_resilience.py || echo "Note: verify_resilience.py may require httpx locally. If it fails, check logs in Docker."

logs:
	docker compose logs -f

seed:
	./scripts/seed_data.sh

status:
	docker compose ps

# Observability UIs (MacOS specific open command)
jaeger:
	open http://localhost:16686

prometheus:
	open http://localhost:9090

grafana:
	open http://localhost:3000

# flink-ui:
# 	open http://localhost:8081

# minio-ui:
# 	open http://localhost:9001

cdc-setup:
	@echo "Setting up Debezium Postgres Connectors..."
	curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" localhost:8083/connectors/ -d @infra/debezium/postgres-connector.json
	curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" localhost:8083/connectors/ -d @infra/debezium/order-outbox-connector.json

loki:
	@echo "Loki logs are best viewed in Grafana (http://localhost:3000)"
	@echo "Direct API: http://localhost:3100"
	open http://localhost:3000

kafka-ui:
	open http://localhost:8080

envoy-admin:
	open http://localhost:9901

envoy-logs:
	docker compose -f docker-compose.dev.yml logs -f envoy

redis-insight:
	open http://localhost:8003

redis-commander:
	open http://localhost:8082

flink-ui:
	open http://localhost:8081

clickhouse-ui:
	@echo "ClickHouse HTTP Interface: http://localhost:8123"
	open http://localhost:8123/play

minio-ui:
	open http://localhost:9001

es-health:
	curl http://localhost:9200/_cluster/health?pretty

kafka-dlq-topics:
	@echo "Creating DLQ topics..."
	docker compose exec kafka kafka-topics --create --if-not-exists --topic inventory.dlq --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
	docker compose exec kafka kafka-topics --create --if-not-exists --topic order-streamer.dlq --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
	docker compose exec kafka kafka-topics --create --if-not-exists --topic analytics.dlq --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

replay-inventory:
	@echo "Replaying inventory DLQ via API..."
	curl -X POST http://localhost:8087/api/replay -H "Content-Type: application/json" -d '{"source": "inventory.dlq", "target": "order-events"}'

replay-order-streamer:
	@echo "Replaying order-streamer DLQ via API..."
	curl -X POST http://localhost:8087/api/replay -H "Content-Type: application/json" -d '{"source": "order-streamer.dlq", "target": "order-events"}'

replay-analytics:
	@echo "Replaying analytics DLQ via API..."
	curl -X POST http://localhost:8087/api/replay -H "Content-Type: application/json" -d '{"source": "analytics.dlq", "target": "order-events"}'

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Build & Run:"
	@echo "  generate     - Generate gRPC code"
	@echo "  up           - Start entire stack in background"
	@echo "  up-dev       - Start stack in dev mode (hot-reload)"
	@echo "  down         - Stop all services"
	@echo "  restart      - Restart all services"
	@echo "  clean        - Remove generated files"
	@echo ""
	@echo "Test & Data:"
	@echo "  test         - Run basic end-to-end test"
	@echo "  seed         - Generate random orders for observability demo"
	@echo ""
	@echo "Monitoring & Observability:"
	@echo "  logs         - Follow service logs"
	@echo "  status       - Show running containers"
	@echo "  jaeger       - Open Jaeger UI (Tracing)"
	@echo "  prometheus   - Open Prometheus UI (Metrics)"
	@echo "  grafana      - Open Grafana UI (Dashboards & Loki Logs)"
	@echo "  loki         - Alias for Grafana (viewing logs)"
	@echo "  kafka-ui     - Open Kafka UI (Topics & Messages)"
	@echo "  redis-insight - Open RedisInsight Dashboard"
	@echo "  redis-commander - Open Redis Commander UI"
	@echo "  envoy-admin   - Open Envoy Admin UI (Metrics & Cluster stats)"
	@echo "  envoy-logs    - Follow Envoy proxy logs"
	@echo "  flink-ui      - Open Flink UI"
	@echo "  clickhouse-ui - Open ClickHouse UI"
	@echo "  minio-ui      - Open MinIO UI"
	@echo "  es-health     - Check Elasticsearch cluster health"
	@echo "  kafka-dlq-topics - Create DLQ Kafka topics"
	@echo "  replay-inventory      - Replay inventory DLQ events"
	@echo "  replay-order-streamer - Replay order-streamer DLQ events"
	@echo "  replay-analytics      - Replay analytics DLQ events"

.DEFAULT_GOAL := help
