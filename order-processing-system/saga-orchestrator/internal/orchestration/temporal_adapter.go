package orchestration

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	enumspb "go.temporal.io/api/enums/v1"
	"go.temporal.io/api/serviceerror"
	"go.temporal.io/sdk/client"

	workflowv1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/temporal/workflow"
	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
)

type TemporalAdapter struct {
	client    client.Client
	taskQueue string
}

func NewTemporalAdapter(c client.Client, taskQueue string) *TemporalAdapter {
	return &TemporalAdapter{client: c, taskQueue: taskQueue}
}

func (t *TemporalAdapter) StartOrderSaga(ctx context.Context, req *sagav1.StartOrderSagaRequest) (string, error) {
	workflowID := fmt.Sprintf("order-saga-%s", req.OrderId)

	items := make([]workflowv1.OrderItem, 0, len(req.Items))
	for _, item := range req.Items {
		items = append(items, workflowv1.OrderItem{
			ProductID:  item.ProductId,
			Quantity:   item.Quantity,
			PriceCents: item.PriceCents,
		})
	}

	input := workflowv1.OrderFulfillmentInput{
		SagaID:     workflowID,
		OrderID:    req.OrderId,
		CustomerID: req.CustomerId,
		Items:      items,
	}

	options := client.StartWorkflowOptions{
		ID:                       workflowID,
		TaskQueue:                t.taskQueue,
		WorkflowRunTimeout:       24 * time.Hour,
		WorkflowExecutionTimeout: 7 * 24 * time.Hour,
	}

	execution, err := t.client.ExecuteWorkflow(ctx, options, workflowv1.WorkflowOrderFulfillment, input)
	if err != nil {
		if _, ok := err.(*serviceerror.WorkflowExecutionAlreadyStarted); ok {
			return workflowID, nil
		}
		return "", err
	}
	return execution.GetID(), nil
}

func (t *TemporalAdapter) GetSagaStatus(ctx context.Context, workflowID string) (*SagaStatus, error) {
	describe, err := t.client.DescribeWorkflowExecution(ctx, workflowID, "")
	if err != nil {
		if _, ok := err.(*serviceerror.NotFound); ok {
			return nil, ErrSagaNotFound
		}
		return nil, err
	}

	status := mapExecutionStatus(describe.WorkflowExecutionInfo.Status)
	currentTask := "UNKNOWN"
	outputData := map[string]interface{}{}

	if describe.WorkflowExecutionInfo.Status == enumspb.WORKFLOW_EXECUTION_STATUS_RUNNING {
		var queried workflowv1.OrderFulfillmentResult
		q, qErr := t.client.QueryWorkflow(ctx, workflowID, "", workflowv1.QuerySagaStatus)
		if qErr == nil && q.Get(&queried) == nil {
			status = queried.Status
			currentTask = queried.CurrentTask
			outputData = asMap(queried)
		}
	} else {
		run := t.client.GetWorkflow(ctx, workflowID, "")
		var result workflowv1.OrderFulfillmentResult
		if getErr := run.Get(ctx, &result); getErr == nil {
			status = result.Status
			currentTask = result.CurrentTask
			outputData = asMap(result)
		}
	}

	return &SagaStatus{
		WorkflowID:  workflowID,
		Status:      status,
		CurrentTask: currentTask,
		OutputData:  outputData,
	}, nil
}

func mapExecutionStatus(status enumspb.WorkflowExecutionStatus) string {
	switch status {
	case enumspb.WORKFLOW_EXECUTION_STATUS_RUNNING:
		return "IN_PROGRESS"
	case enumspb.WORKFLOW_EXECUTION_STATUS_COMPLETED:
		return "COMPLETED"
	case enumspb.WORKFLOW_EXECUTION_STATUS_FAILED:
		return "FAILED"
	case enumspb.WORKFLOW_EXECUTION_STATUS_TIMED_OUT:
		return "FAILED"
	case enumspb.WORKFLOW_EXECUTION_STATUS_TERMINATED:
		return "FAILED"
	case enumspb.WORKFLOW_EXECUTION_STATUS_CANCELED:
		return "FAILED"
	default:
		return "UNKNOWN"
	}
}

func asMap(value interface{}) map[string]interface{} {
	if value == nil {
		return map[string]interface{}{}
	}
	payload, err := json.Marshal(value)
	if err != nil {
		return map[string]interface{}{}
	}
	output := map[string]interface{}{}
	if err := json.Unmarshal(payload, &output); err != nil {
		return map[string]interface{}{}
	}
	return output
}
