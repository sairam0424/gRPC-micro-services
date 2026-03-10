package worker

import (
	"context"
	"sync"
	"testing"

	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"

	workflowv1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/temporal/workflow"
)

type scriptedExecutor struct {
	mu        sync.Mutex
	responses map[string]*CommandResponse
	errors    map[string]error
	calls     []string
}

func (s *scriptedExecutor) ExecuteCommand(ctx context.Context, req CommandRequest) (*CommandResponse, error) {
	_ = ctx
	s.mu.Lock()
	defer s.mu.Unlock()
	s.calls = append(s.calls, req.Command)
	if err := s.errors[req.Command]; err != nil {
		return nil, err
	}
	resp := s.responses[req.Command]
	if resp == nil {
		return &CommandResponse{Status: "SUCCESS"}, nil
	}
	return resp, nil
}

func TestTemporalWorkflowAndActivities_EndToEnd(t *testing.T) {
	executor := &scriptedExecutor{
		responses: map[string]*CommandResponse{
			"reserve_stock":  {Status: "SUCCESS"},
			"complete_order": {Status: "SUCCESS"},
		},
		errors: map[string]error{},
	}

	activities := NewActivities(executor)
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	env.RegisterWorkflow(workflowv1.OrderFulfillmentWorkflow)
	env.RegisterActivityWithOptions(activities.ReserveStock, activity.RegisterOptions{Name: workflowv1.ActivityReserveStock})
	env.RegisterActivityWithOptions(activities.CompleteOrder, activity.RegisterOptions{Name: workflowv1.ActivityCompleteOrder})
	env.RegisterActivityWithOptions(activities.ReleaseStock, activity.RegisterOptions{Name: workflowv1.ActivityReleaseStock})
	env.RegisterActivityWithOptions(activities.FailOrder, activity.RegisterOptions{Name: workflowv1.ActivityFailOrder})

	env.ExecuteWorkflow(workflowv1.OrderFulfillmentWorkflow, workflowv1.OrderFulfillmentInput{
		SagaID:  "order-saga-100",
		OrderID: "ORD-100",
	})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())

	var result workflowv1.OrderFulfillmentResult
	require.NoError(t, env.GetWorkflowResult(&result))
	require.Equal(t, "COMPLETED", result.Status)
	require.Equal(t, []string{"reserve_stock", "complete_order"}, result.CompletedSteps)
	require.Equal(t, []string{"reserve_stock", "complete_order"}, executor.calls)
}

func TestTemporalWorkflowAndActivities_FailurePathCompensationOrder(t *testing.T) {
	executor := &scriptedExecutor{
		responses: map[string]*CommandResponse{
			"reserve_stock":  {Status: "SUCCESS"},
			"complete_order": {Status: "FAILURE", Error: "temporary outage"},
			"release_stock":  {Status: "SUCCESS"},
			"fail_order":     {Status: "SUCCESS"},
		},
		errors: map[string]error{},
	}

	activities := NewActivities(executor)
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	env.RegisterWorkflow(workflowv1.OrderFulfillmentWorkflow)
	env.RegisterActivityWithOptions(activities.ReserveStock, activity.RegisterOptions{Name: workflowv1.ActivityReserveStock})
	env.RegisterActivityWithOptions(activities.CompleteOrder, activity.RegisterOptions{Name: workflowv1.ActivityCompleteOrder})
	env.RegisterActivityWithOptions(activities.ReleaseStock, activity.RegisterOptions{Name: workflowv1.ActivityReleaseStock})
	env.RegisterActivityWithOptions(activities.FailOrder, activity.RegisterOptions{Name: workflowv1.ActivityFailOrder})

	env.ExecuteWorkflow(workflowv1.OrderFulfillmentWorkflow, workflowv1.OrderFulfillmentInput{
		SagaID:  "order-saga-101",
		OrderID: "ORD-101",
	})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())

	var result workflowv1.OrderFulfillmentResult
	require.NoError(t, env.GetWorkflowResult(&result))
	require.Equal(t, "FAILED", result.Status)
	require.GreaterOrEqual(t, len(executor.calls), 4)
	require.Equal(t, "reserve_stock", executor.calls[0])
	completeCount := 0
	for _, call := range executor.calls {
		if call == "complete_order" {
			completeCount++
		}
	}
	require.GreaterOrEqual(t, completeCount, 1)
	require.Equal(t, "release_stock", executor.calls[len(executor.calls)-2])
	require.Equal(t, "fail_order", executor.calls[len(executor.calls)-1])
	require.Contains(t, result.CompensatedSteps, "release_stock")
	require.Contains(t, result.CompensatedSteps, "fail_order")
}
