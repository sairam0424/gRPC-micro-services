package workflow

import (
	"errors"
	"fmt"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

const (
	WorkflowOrderFulfillment = "OrderFulfillmentWorkflow"
	QuerySagaStatus          = "status"
	SignalForceCompensate    = "force_compensate"

	ActivityReserveStock  = "ReserveStockActivity"
	ActivityCompleteOrder = "CompleteOrderActivity"
	ActivityReleaseStock  = "ReleaseStockActivity"
	ActivityFailOrder     = "FailOrderActivity"
)

type OrderItem struct {
	ProductID  string `json:"product_id"`
	Quantity   uint32 `json:"quantity"`
	PriceCents int64  `json:"price_cents"`
}

type SagaActivityInput struct {
	SagaID         string                 `json:"saga_id"`
	OrderID        string                 `json:"order_id"`
	CustomerID     string                 `json:"customer_id"`
	Command        string                 `json:"command"`
	Items          []OrderItem            `json:"items,omitempty"`
	Reason         string                 `json:"reason,omitempty"`
	IdempotencyKey string                 `json:"idempotency_key"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
}

type SagaActivityResult struct {
	Status  string                 `json:"status"`
	Message string                 `json:"message,omitempty"`
	Data    map[string]interface{} `json:"data,omitempty"`
}

type OrderFulfillmentInput struct {
	SagaID     string      `json:"saga_id"`
	OrderID    string      `json:"order_id"`
	CustomerID string      `json:"customer_id"`
	Items      []OrderItem `json:"items"`
}

type AuditRecord struct {
	Step       string    `json:"step"`
	Phase      string    `json:"phase"`
	Status     string    `json:"status"`
	OccurredAt time.Time `json:"occurred_at"`
	Error      string    `json:"error,omitempty"`
}

type OrderFulfillmentResult struct {
	SagaID            string        `json:"saga_id"`
	OrderID           string        `json:"order_id"`
	Status            string        `json:"status"`
	CurrentTask       string        `json:"current_task"`
	CompletedSteps    []string      `json:"completed_steps"`
	CompensatedSteps  []string      `json:"compensated_steps"`
	FailureType       string        `json:"failure_type,omitempty"`
	LastError         string        `json:"last_error,omitempty"`
	CompensationState string        `json:"compensation_state,omitempty"`
	AuditTrail        []AuditRecord `json:"audit_trail"`
}

func OrderFulfillmentWorkflow(ctx workflow.Context, input OrderFulfillmentInput) (OrderFulfillmentResult, error) {
	result := OrderFulfillmentResult{
		SagaID:      input.SagaID,
		OrderID:     input.OrderID,
		Status:      "STARTED",
		CurrentTask: "RESERVE_STOCK",
		AuditTrail:  make([]AuditRecord, 0, 8),
	}

	signalCh := workflow.GetSignalChannel(ctx, SignalForceCompensate)

	if err := workflow.SetQueryHandler(ctx, QuerySagaStatus, func() (OrderFulfillmentResult, error) {
		return result, nil
	}); err != nil {
		return result, err
	}

	activityOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 45 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    15 * time.Second,
			MaximumAttempts:    5,
			NonRetryableErrorTypes: []string{
				"BusinessFailure",
			},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, activityOpts)

	reserveInput := SagaActivityInput{
		SagaID:         input.SagaID,
		OrderID:        input.OrderID,
		CustomerID:     input.CustomerID,
		Command:        "reserve_stock",
		Items:          input.Items,
		IdempotencyKey: fmt.Sprintf("%s:reserve_stock", input.SagaID),
	}

	result.Status = "IN_PROGRESS"
	reserveStep := "RESERVE_STOCK"
	result = appendAudit(ctx, result, reserveStep, "FORWARD", "STARTED", "")

	var reserveRes SagaActivityResult
	if err := workflow.ExecuteActivity(ctx, ActivityReserveStock, reserveInput).Get(ctx, &reserveRes); err != nil {
		result.LastError = err.Error()
		result.FailureType = classifyFailure(err)
		result = appendAudit(ctx, result, reserveStep, "FORWARD", "FAILED", err.Error())
		return failOrderOnly(ctx, result, input, "reserve_stock_failed")
	}

	result.CompletedSteps = append(result.CompletedSteps, "reserve_stock")
	result = appendAudit(ctx, result, reserveStep, "FORWARD", "COMPLETED", "")

	completeInput := SagaActivityInput{
		SagaID:         input.SagaID,
		OrderID:        input.OrderID,
		CustomerID:     input.CustomerID,
		Command:        "complete_order",
		IdempotencyKey: fmt.Sprintf("%s:complete_order", input.SagaID),
	}
	result.CurrentTask = "COMPLETE_ORDER"
	result = appendAudit(ctx, result, "COMPLETE_ORDER", "FORWARD", "STARTED", "")

	var completeRes SagaActivityResult
	if err := workflow.ExecuteActivity(ctx, ActivityCompleteOrder, completeInput).Get(ctx, &completeRes); err != nil {
		result.LastError = err.Error()
		result.FailureType = classifyFailure(err)
		result = appendAudit(ctx, result, "COMPLETE_ORDER", "FORWARD", "FAILED", err.Error())
		return compensateReserveThenFail(ctx, result, input, "complete_order_failed")
	}

	if signalReceived(signalCh) {
		result = appendAudit(ctx, result, "FORCE_COMPENSATE", "CONTROL", "STARTED", "operator signal")
		return compensateReserveThenFail(ctx, result, input, "force_compensate")
	}

	result.CompletedSteps = append(result.CompletedSteps, "complete_order")
	result.Status = "COMPLETED"
	result.CurrentTask = "DONE"
	result = appendAudit(ctx, result, "COMPLETE_ORDER", "FORWARD", "COMPLETED", "")
	return result, nil
}

func failOrderOnly(ctx workflow.Context, result OrderFulfillmentResult, input OrderFulfillmentInput, reason string) (OrderFulfillmentResult, error) {
	result.Status = "COMPENSATING"
	result.CompensationState = "IN_PROGRESS"
	result.CurrentTask = "FAIL_ORDER"
	result = appendAudit(ctx, result, "FAIL_ORDER", "COMPENSATION", "STARTED", "")

	failInput := SagaActivityInput{
		SagaID:         input.SagaID,
		OrderID:        input.OrderID,
		CustomerID:     input.CustomerID,
		Command:        "fail_order",
		Reason:         reason,
		IdempotencyKey: fmt.Sprintf("%s:fail_order", input.SagaID),
		Metadata: map[string]interface{}{
			"failureReason": result.LastError,
		},
	}

	var failRes SagaActivityResult
	if err := workflow.ExecuteActivity(ctx, ActivityFailOrder, failInput).Get(ctx, &failRes); err != nil {
		result = appendAudit(ctx, result, "FAIL_ORDER", "COMPENSATION", "FAILED", err.Error())
		result.CompensationState = "FAILED"
		result.Status = "FAILED"
		result.CurrentTask = "FAILED"
		if result.LastError == "" {
			result.LastError = err.Error()
		}
		return result, nil
	}

	result.CompensatedSteps = append(result.CompensatedSteps, "fail_order")
	result = appendAudit(ctx, result, "FAIL_ORDER", "COMPENSATION", "COMPLETED", "")
	result.CompensationState = "COMPLETED"
	result.Status = "FAILED"
	result.CurrentTask = "FAILED"
	return result, nil
}

func compensateReserveThenFail(ctx workflow.Context, result OrderFulfillmentResult, input OrderFulfillmentInput, reason string) (OrderFulfillmentResult, error) {
	result.Status = "COMPENSATING"
	result.CompensationState = "IN_PROGRESS"

	if contains(result.CompletedSteps, "reserve_stock") {
		releaseInput := SagaActivityInput{
			SagaID:         input.SagaID,
			OrderID:        input.OrderID,
			CustomerID:     input.CustomerID,
			Command:        "release_stock",
			Items:          input.Items,
			IdempotencyKey: fmt.Sprintf("%s:release_stock", input.SagaID),
		}
		result.CurrentTask = "RELEASE_STOCK"
		result = appendAudit(ctx, result, "RELEASE_STOCK", "COMPENSATION", "STARTED", "")

		var releaseRes SagaActivityResult
		if err := workflow.ExecuteActivity(ctx, ActivityReleaseStock, releaseInput).Get(ctx, &releaseRes); err != nil {
			result = appendAudit(ctx, result, "RELEASE_STOCK", "COMPENSATION", "FAILED", err.Error())
			if result.LastError == "" {
				result.LastError = err.Error()
			}
		} else {
			result.CompensatedSteps = append(result.CompensatedSteps, "release_stock")
			result = appendAudit(ctx, result, "RELEASE_STOCK", "COMPENSATION", "COMPLETED", "")
		}
	}

	failedResult, err := failOrderOnly(ctx, result, input, reason)
	if failedResult.CompensationState != "FAILED" {
		failedResult.CompensationState = "COMPLETED"
	}
	return failedResult, err
}

func appendAudit(ctx workflow.Context, result OrderFulfillmentResult, step string, phase string, status string, errMsg string) OrderFulfillmentResult {
	record := AuditRecord{
		Step:       step,
		Phase:      phase,
		Status:     status,
		OccurredAt: workflow.Now(ctx),
		Error:      errMsg,
	}
	result.AuditTrail = append(result.AuditTrail, record)
	return result
}

func contains(values []string, candidate string) bool {
	for _, v := range values {
		if v == candidate {
			return true
		}
	}
	return false
}

func classifyFailure(err error) string {
	var appErr *temporal.ApplicationError
	if errors.As(err, &appErr) && appErr.NonRetryable() {
		return "BUSINESS"
	}
	return "TECHNICAL"
}

func signalReceived(ch workflow.ReceiveChannel) bool {
	if ch == nil {
		return false
	}
	var value bool
	ok := ch.ReceiveAsync(&value)
	return ok
}
