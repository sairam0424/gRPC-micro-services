package service

import (
	"context"
	"errors"
	"log"

	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/orchestration"
	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"
)

type SagaService struct {
	sagav1.UnimplementedSagaServiceServer
	orchestrator *orchestration.Router
}

func NewSagaService(orchestrator *orchestration.Router) *SagaService {
	return &SagaService{
		orchestrator: orchestrator,
	}
}

func (s *SagaService) StartOrderSaga(ctx context.Context, req *sagav1.StartOrderSagaRequest) (*sagav1.StartOrderSagaResponse, error) {
	log.Printf("Saga Orchestrator: Starting Order Saga for %s", req.OrderId)

	sagaID, err := s.orchestrator.StartOrderSaga(ctx, req)
	if err != nil {
		log.Printf("Saga Orchestrator: Failed to start saga: %v", err)
		return nil, status.Errorf(codes.Internal, "failed to initiate saga workflow")
	}

	return &sagav1.StartOrderSagaResponse{
		WorkflowId: sagaID,
		Status:     "STARTED",
	}, nil
}

func (s *SagaService) GetSagaStatus(ctx context.Context, req *sagav1.GetSagaStatusRequest) (*sagav1.GetSagaStatusResponse, error) {
	sagaStatus, err := s.orchestrator.GetSagaStatus(ctx, req.WorkflowId)
	if err != nil {
		log.Printf("Saga Orchestrator: Failed to get saga %s: %v", req.WorkflowId, err)
		if errors.Is(err, orchestration.ErrSagaNotFound) {
			return nil, status.Errorf(codes.NotFound, "saga instance not found")
		}
		return nil, status.Errorf(codes.Internal, "failed to fetch saga status")
	}

	outputData, err := structpb.NewStruct(sagaStatus.OutputData)
	if err != nil {
		log.Printf("Saga Orchestrator: CRITICAL: Failed to convert instance data to structpb: %v", err)
		// We still return the status even if data conversion fails
	}

	return &sagav1.GetSagaStatusResponse{
		WorkflowId:  sagaStatus.WorkflowID,
		Status:      sagaStatus.Status,
		CurrentTask: sagaStatus.CurrentTask,
		OutputData:  outputData,
	}, nil
}
