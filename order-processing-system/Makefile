.PHONY: generate clean build-python build-go up down

PROTOC_GEN_GO := $(shell which protoc-gen-go)
PROTOC_GEN_GO_GRPC := $(shell which protoc-gen-go-grpc)

generate:
	@echo "Generating Python gRPC code..."
	mkdir -p api-gateway/src/generated
	python -m grpc_tools.protoc -I. -I./proto --python_out=api-gateway/src/generated --grpc_python_out=api-gateway/src/generated proto/order/v1/order.proto
	touch api-gateway/src/generated/__init__.py
	
	@echo "Generating Go gRPC code..."
	mkdir -p order-service/pkg/generated
	export PATH=$$PATH:$$(go env GOPATH)/bin && \
	protoc -Iproto -I. -I/usr/local/include \
	    --go_out=order-service/pkg/generated --go_opt=paths=source_relative \
	    --go-grpc_out=order-service/pkg/generated --go-grpc_opt=paths=source_relative \
	    --grpc-gateway_out=order-service/pkg/generated --grpc-gateway_opt=paths=source_relative \
	    --openapiv2_out=order-service/pkg/generated \
	    proto/order/v1/order.proto
	
	@echo "Validating OpenAPI spec with go-swagger..."
	export PATH=$$PATH:$$(go env GOPATH)/bin && \
	swagger validate order-service/pkg/generated/proto/order/v1/order.swagger.json

clean:
	rm -rf api-gateway/src/generated/*
	rm -rf order-service/pkg/generated/*

up:
	docker-compose up --build

up-dev:
	docker-compose -f docker-compose.dev.yml up --build

down:
	docker-compose down
