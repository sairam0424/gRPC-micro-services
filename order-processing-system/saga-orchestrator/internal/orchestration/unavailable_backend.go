package orchestration

import (
	"context"
	"fmt"

	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
)

type UnavailableBackend struct {
	name string
	err  error
}

func NewUnavailableBackend(name string, err error) *UnavailableBackend {
	return &UnavailableBackend{name: name, err: err}
}

func (u *UnavailableBackend) StartOrderSaga(ctx context.Context, req *sagav1.StartOrderSagaRequest) (string, error) {
	_ = ctx
	_ = req
	if u.err != nil {
		return "", fmt.Errorf("%s backend unavailable: %w", u.name, u.err)
	}
	return "", fmt.Errorf("%s backend unavailable", u.name)
}

func (u *UnavailableBackend) GetSagaStatus(ctx context.Context, workflowID string) (*SagaStatus, error) {
	_ = ctx
	_ = workflowID
	return nil, ErrSagaNotFound
}
