package orchestration

import (
	"context"

	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
)

const (
	RouteLegacy   = "legacy"
	RouteTemporal = "temporal"
	RouteCanary   = "canary"
)

type SagaStatus struct {
	WorkflowID  string
	Status      string
	CurrentTask string
	OutputData  map[string]interface{}
}

type Backend interface {
	StartOrderSaga(ctx context.Context, req *sagav1.StartOrderSagaRequest) (string, error)
	GetSagaStatus(ctx context.Context, workflowID string) (*SagaStatus, error)
}

type RouteStore interface {
	Set(ctx context.Context, workflowID string, route string) error
	Get(ctx context.Context, workflowID string) (string, error)
}
