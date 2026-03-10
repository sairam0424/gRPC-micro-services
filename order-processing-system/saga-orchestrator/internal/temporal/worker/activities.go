package worker

import (
	"context"
	"fmt"
	"log"
	"strings"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/temporal"

	workflowv1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/temporal/workflow"
)

type Activities struct {
	executor CommandExecutor
}

func NewActivities(executor CommandExecutor) *Activities {
	return &Activities{executor: executor}
}

func (a *Activities) ReserveStock(ctx context.Context, input workflowv1.SagaActivityInput) (*workflowv1.SagaActivityResult, error) {
	return a.execute(ctx, input, "reserve_stock")
}

func (a *Activities) CompleteOrder(ctx context.Context, input workflowv1.SagaActivityInput) (*workflowv1.SagaActivityResult, error) {
	return a.execute(ctx, input, "complete_order")
}

func (a *Activities) ReleaseStock(ctx context.Context, input workflowv1.SagaActivityInput) (*workflowv1.SagaActivityResult, error) {
	return a.execute(ctx, input, "release_stock")
}

func (a *Activities) FailOrder(ctx context.Context, input workflowv1.SagaActivityInput) (*workflowv1.SagaActivityResult, error) {
	return a.execute(ctx, input, "fail_order")
}

func (a *Activities) execute(ctx context.Context, input workflowv1.SagaActivityInput, command string) (*workflowv1.SagaActivityResult, error) {
	input.Command = command
	workflowID, runID := safeActivityExecutionInfo(ctx)
	log.Printf(
		"Executing temporal saga activity workflowId=%s runId=%s sagaId=%s orderId=%s command=%s idempotencyKey=%s",
		workflowID, runID, input.SagaID, input.OrderID, command, input.IdempotencyKey,
	)

	data := map[string]interface{}{}
	if len(input.Items) > 0 {
		items := make([]map[string]interface{}, 0, len(input.Items))
		for _, item := range input.Items {
			items = append(items, map[string]interface{}{
				"product_id":  item.ProductID,
				"quantity":    item.Quantity,
				"price_cents": item.PriceCents,
			})
		}
		data["items"] = items
	}
	if input.Reason != "" {
		data["reason"] = input.Reason
	}
	if len(input.Metadata) > 0 {
		for k, v := range input.Metadata {
			data[k] = v
		}
	}

	response, err := a.executor.ExecuteCommand(ctx, CommandRequest{
		SagaID:         input.SagaID,
		OrderID:        input.OrderID,
		Command:        command,
		Data:           data,
		IdempotencyKey: input.IdempotencyKey,
	})
	if err != nil {
		if isBusinessError(err) {
			return nil, temporal.NewNonRetryableApplicationError(err.Error(), "BusinessFailure", nil)
		}
		return nil, fmt.Errorf("execute command %s: %w", command, err)
	}

	if response == nil {
		return nil, fmt.Errorf("empty response for command %s", command)
	}

	result := &workflowv1.SagaActivityResult{
		Status:  strings.ToUpper(strings.TrimSpace(response.Status)),
		Message: response.Error,
		Data:    response.Data,
	}

	if result.Status == "" {
		result.Status = "SUCCESS"
	}
	if strings.EqualFold(result.Status, "FAILURE") {
		if isBusinessMessage(response.Error) {
			return nil, temporal.NewNonRetryableApplicationError(response.Error, "BusinessFailure", nil)
		}
		return nil, fmt.Errorf("command %s returned failure: %s", command, response.Error)
	}

	log.Printf("Temporal Activity %s completed for Saga %s", command, input.SagaID)
	return result, nil
}

func isBusinessError(err error) bool {
	if err == nil {
		return false
	}
	return isBusinessMessage(err.Error())
}

func isBusinessMessage(msg string) bool {
	m := strings.ToLower(msg)
	keywords := []string{
		"insufficient stock",
		"out of stock",
		"not found",
		"already reserved",
		"invalid",
	}
	for _, keyword := range keywords {
		if strings.Contains(m, keyword) {
			return true
		}
	}
	return false
}

func safeActivityExecutionInfo(ctx context.Context) (workflowID string, runID string) {
	defer func() {
		if recover() != nil {
			workflowID = ""
			runID = ""
		}
	}()
	info := activity.GetInfo(ctx)
	return info.WorkflowExecution.ID, info.WorkflowExecution.RunID
}
