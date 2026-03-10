package worker

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/temporal"

	workflowv1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/temporal/workflow"
)

type fakeExecutor struct {
	response *CommandResponse
	err      error
	lastReq  CommandRequest
}

func (f *fakeExecutor) ExecuteCommand(ctx context.Context, req CommandRequest) (*CommandResponse, error) {
	_ = ctx
	f.lastReq = req
	return f.response, f.err
}

func TestActivities_ReserveStock_ClassifiesBusinessErrorsAsNonRetryable(t *testing.T) {
	executor := &fakeExecutor{err: context.DeadlineExceeded}
	activities := NewActivities(executor)

	_, err := activities.ReserveStock(context.Background(), workflowv1.SagaActivityInput{SagaID: "saga-1", OrderID: "ORD-1"})
	require.Error(t, err)
	var appErr *temporal.ApplicationError
	require.False(t, errors.As(err, &appErr) && appErr.NonRetryable())

	executor.err = nil
	executor.response = &CommandResponse{Status: "FAILURE", Error: "insufficient stock for PROD-1"}
	_, err = activities.ReserveStock(context.Background(), workflowv1.SagaActivityInput{SagaID: "saga-1", OrderID: "ORD-1"})
	require.Error(t, err)
	require.True(t, errors.As(err, &appErr) && appErr.NonRetryable())
}

func TestActivities_ReleaseStock_PassesIdempotencyKey(t *testing.T) {
	executor := &fakeExecutor{response: &CommandResponse{Status: "SUCCESS"}}
	activities := NewActivities(executor)

	_, err := activities.ReleaseStock(context.Background(), workflowv1.SagaActivityInput{
		SagaID:         "saga-2",
		OrderID:        "ORD-2",
		IdempotencyKey: "saga-2:release_stock",
		Items: []workflowv1.OrderItem{{
			ProductID: "PROD-2",
			Quantity:  2,
		}},
	})
	require.NoError(t, err)
	require.Equal(t, "release_stock", executor.lastReq.Command)
	require.Equal(t, "saga-2:release_stock", executor.lastReq.IdempotencyKey)
	items, ok := executor.lastReq.Data["items"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, items, 1)
	require.Equal(t, "PROD-2", items[0]["product_id"])
}
