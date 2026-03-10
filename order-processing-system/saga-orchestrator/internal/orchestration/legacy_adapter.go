package orchestration

import (
	"context"
	"errors"

	"github.com/redis/go-redis/v9"
	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/engine"
	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
)

type LegacyAdapter struct {
	engine *engine.SagaEngine
}

func NewLegacyAdapter(e *engine.SagaEngine) *LegacyAdapter {
	return &LegacyAdapter{engine: e}
}

func (l *LegacyAdapter) StartOrderSaga(ctx context.Context, req *sagav1.StartOrderSagaRequest) (string, error) {
	return l.engine.StartOrderSaga(ctx, req.OrderId, req.Items)
}

func (l *LegacyAdapter) GetSagaStatus(ctx context.Context, workflowID string) (*SagaStatus, error) {
	instance, err := l.engine.GetSaga(ctx, workflowID)
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return nil, ErrSagaNotFound
		}
		return nil, err
	}

	return &SagaStatus{
		WorkflowID:  instance.ID,
		Status:      string(instance.Status),
		CurrentTask: instance.CurrentStep,
		OutputData:  instance.Data,
	}, nil
}

func (l *LegacyAdapter) StartEventLoop(ctx context.Context) {
	l.engine.Start(ctx)
}
