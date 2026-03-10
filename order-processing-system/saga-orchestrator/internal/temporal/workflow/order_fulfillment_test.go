package workflow

import (
	"context"
	"testing"

	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/testsuite"
)

func TestOrderFulfillmentWorkflow_HappyPath(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	defer env.AssertExpectations(t)

	env.RegisterWorkflow(OrderFulfillmentWorkflow)
	registerNamedActivities(env)
	env.OnActivity(ActivityReserveStock, mock.Anything, mock.Anything).Return(&SagaActivityResult{Status: "SUCCESS"}, nil).Once()
	env.OnActivity(ActivityCompleteOrder, mock.Anything, mock.Anything).Return(&SagaActivityResult{Status: "SUCCESS"}, nil).Once()

	env.ExecuteWorkflow(OrderFulfillmentWorkflow, OrderFulfillmentInput{
		SagaID:     "order-saga-1",
		OrderID:    "ORD-1",
		CustomerID: "CUST-1",
		Items: []OrderItem{{
			ProductID:  "PROD-1",
			Quantity:   1,
			PriceCents: 1000,
		}},
	})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())

	var result OrderFulfillmentResult
	require.NoError(t, env.GetWorkflowResult(&result))
	require.Equal(t, "COMPLETED", result.Status)
	require.Equal(t, "DONE", result.CurrentTask)
	require.Contains(t, result.CompletedSteps, "reserve_stock")
	require.Contains(t, result.CompletedSteps, "complete_order")
	require.Empty(t, result.CompensatedSteps)
}

func TestOrderFulfillmentWorkflow_ReserveBusinessFailure_CompensatesWithFailOrderOnly(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	defer env.AssertExpectations(t)

	env.RegisterWorkflow(OrderFulfillmentWorkflow)
	registerNamedActivities(env)
	env.OnActivity(ActivityReserveStock, mock.Anything, mock.Anything).
		Return((*SagaActivityResult)(nil), temporal.NewNonRetryableApplicationError("insufficient stock", "BusinessFailure", nil)).
		Once()
	env.OnActivity(ActivityFailOrder, mock.Anything, mock.Anything).Return(&SagaActivityResult{Status: "SUCCESS"}, nil).Once()

	env.ExecuteWorkflow(OrderFulfillmentWorkflow, OrderFulfillmentInput{SagaID: "order-saga-2", OrderID: "ORD-2"})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())

	var result OrderFulfillmentResult
	require.NoError(t, env.GetWorkflowResult(&result))
	require.Equal(t, "FAILED", result.Status)
	require.NotContains(t, result.CompensatedSteps, "release_stock")
	require.Contains(t, result.CompensatedSteps, "fail_order")
	require.Equal(t, "BUSINESS", result.FailureType)
}

func TestOrderFulfillmentWorkflow_CompleteFailure_CompensatesInReverseOrder(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	defer env.AssertExpectations(t)

	env.RegisterWorkflow(OrderFulfillmentWorkflow)
	registerNamedActivities(env)
	env.OnActivity(ActivityReserveStock, mock.Anything, mock.Anything).Return(&SagaActivityResult{Status: "SUCCESS"}, nil).Once()
	env.OnActivity(ActivityCompleteOrder, mock.Anything, mock.Anything).
		Return((*SagaActivityResult)(nil), temporal.NewApplicationError("db timeout", "TechnicalFailure")).
		Once()
	env.OnActivity(ActivityReleaseStock, mock.Anything, mock.Anything).Return(&SagaActivityResult{Status: "SUCCESS"}, nil).Once()
	env.OnActivity(ActivityFailOrder, mock.Anything, mock.Anything).Return(&SagaActivityResult{Status: "SUCCESS"}, nil).Once()

	env.ExecuteWorkflow(OrderFulfillmentWorkflow, OrderFulfillmentInput{SagaID: "order-saga-3", OrderID: "ORD-3"})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())

	var result OrderFulfillmentResult
	require.NoError(t, env.GetWorkflowResult(&result))
	require.Equal(t, "FAILED", result.Status)
	require.Equal(t, "COMPLETED", result.CompensationState)
	require.Contains(t, result.CompensatedSteps, "release_stock")
	require.Contains(t, result.CompensatedSteps, "fail_order")
	require.Equal(t, "TECHNICAL", result.FailureType)
}

func registerNamedActivities(env *testsuite.TestWorkflowEnvironment) {
	noop := func(ctx context.Context, input SagaActivityInput) (*SagaActivityResult, error) {
		_ = ctx
		_ = input
		return &SagaActivityResult{Status: "SUCCESS"}, nil
	}
	env.RegisterActivityWithOptions(noop, activity.RegisterOptions{Name: ActivityReserveStock})
	env.RegisterActivityWithOptions(noop, activity.RegisterOptions{Name: ActivityCompleteOrder})
	env.RegisterActivityWithOptions(noop, activity.RegisterOptions{Name: ActivityReleaseStock})
	env.RegisterActivityWithOptions(noop, activity.RegisterOptions{Name: ActivityFailOrder})
}
