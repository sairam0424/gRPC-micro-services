.PHONY: generate clean build-python build-go up down

PROTOC_GEN_GO := $(shell which protoc-gen-go)
PROTOC_GEN_GO_GRPC := $(shell which protoc-gen-go-grpc)

generate:
	@echo "Generating Python gRPC code..."
	mkdir -p api-gateway/src/generated
	python -m grpc_tools.protoc -I. --python_out=api-gateway/src/generated --grpc_python_out=api-gateway/src/generated proto/order/v1/order.proto
	touch api-gateway/src/generated/__init__.py
	
	@echo "Generating Go gRPC code..."
	mkdir -p order-service/pkg/generated
	protoc --go_out=order-service/pkg/generated --go_opt=paths=source_relative \
	    --go-grpc_out=order-service/pkg/generated --go-grpc_opt=paths=source_relative \
	    proto/order/v1/order.proto

clean:
	rm -rf api-gateway/src/generated/*
	rm -rf order-service/pkg/generated/*

up:
	docker-compose up --build

down:
	docker-compose down
