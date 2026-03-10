package worker

import (
	"context"
	"fmt"
	"log"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"

	workflowv1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/temporal/workflow"
)

type RunnerConfig struct {
	TaskQueue string
}

type Runner struct {
	temporalClient client.Client
	worker         worker.Worker
	gateway        *CommandGateway
	taskQueue      string
}

func NewRunner(ctx context.Context, temporalClient client.Client, cfg RunnerConfig, gatewayCfg GatewayConfig) (*Runner, error) {
	if cfg.TaskQueue == "" {
		return nil, fmt.Errorf("task queue is required")
	}

	gateway, err := NewCommandGateway(gatewayCfg)
	if err != nil {
		return nil, err
	}

	if err := gateway.Start(ctx); err != nil {
		gateway.Close()
		return nil, err
	}

	w := worker.New(temporalClient, cfg.TaskQueue, worker.Options{})
	activities := NewActivities(gateway)

	w.RegisterWorkflowWithOptions(workflowv1.OrderFulfillmentWorkflow, workflow.RegisterOptions{Name: workflowv1.WorkflowOrderFulfillment})
	w.RegisterActivityWithOptions(activities.ReserveStock, activity.RegisterOptions{Name: workflowv1.ActivityReserveStock})
	w.RegisterActivityWithOptions(activities.CompleteOrder, activity.RegisterOptions{Name: workflowv1.ActivityCompleteOrder})
	w.RegisterActivityWithOptions(activities.ReleaseStock, activity.RegisterOptions{Name: workflowv1.ActivityReleaseStock})
	w.RegisterActivityWithOptions(activities.FailOrder, activity.RegisterOptions{Name: workflowv1.ActivityFailOrder})

	return &Runner{
		temporalClient: temporalClient,
		worker:         w,
		gateway:        gateway,
		taskQueue:      cfg.TaskQueue,
	}, nil
}

func (r *Runner) Run(ctx context.Context) error {
	log.Printf("Temporal Worker: starting on task queue %s", r.taskQueue)
	if err := r.worker.Start(); err != nil {
		return fmt.Errorf("start temporal worker: %w", err)
	}

	<-ctx.Done()
	log.Printf("Temporal Worker: shutting down")
	r.worker.Stop()
	r.gateway.Close()
	return nil
}
