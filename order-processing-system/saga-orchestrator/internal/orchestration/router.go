package orchestration

import (
	"context"
	"errors"
	"log"

	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
)

type Router struct {
	legacy   Backend
	temporal Backend
	resolver *RouteResolver
	store    RouteStore
}

func NewRouter(legacy Backend, temporal Backend, resolver *RouteResolver, store RouteStore) *Router {
	return &Router{
		legacy:   legacy,
		temporal: temporal,
		resolver: resolver,
		store:    store,
	}
}

func (r *Router) StartOrderSaga(ctx context.Context, req *sagav1.StartOrderSagaRequest) (string, error) {
	route := r.resolver.Decide(req.OrderId)
	workflowID, err := r.startByRoute(ctx, route, req)
	if err != nil {
		return "", err
	}

	if err := r.store.Set(ctx, workflowID, route); err != nil {
		log.Printf("Saga Router: failed to persist route for workflow %s: %v", workflowID, err)
	}

	return workflowID, nil
}

func (r *Router) startByRoute(ctx context.Context, route string, req *sagav1.StartOrderSagaRequest) (string, error) {
	switch route {
	case RouteTemporal:
		return r.temporal.StartOrderSaga(ctx, req)
	case RouteLegacy:
		fallthrough
	default:
		return r.legacy.StartOrderSaga(ctx, req)
	}
}

func (r *Router) GetSagaStatus(ctx context.Context, workflowID string) (*SagaStatus, error) {
	route, err := r.store.Get(ctx, workflowID)
	if err == nil {
		status, statusErr := r.getByRoute(ctx, route, workflowID)
		if statusErr == nil {
			return status, nil
		}
		if !errors.Is(statusErr, ErrSagaNotFound) {
			return nil, statusErr
		}
	}

	// Route missing or stale; probe temporal then legacy.
	status, temporalErr := r.temporal.GetSagaStatus(ctx, workflowID)
	if temporalErr == nil {
		_ = r.store.Set(ctx, workflowID, RouteTemporal)
		return status, nil
	}
	if temporalErr != nil && !errors.Is(temporalErr, ErrSagaNotFound) {
		return nil, temporalErr
	}

	status, legacyErr := r.legacy.GetSagaStatus(ctx, workflowID)
	if legacyErr == nil {
		_ = r.store.Set(ctx, workflowID, RouteLegacy)
		return status, nil
	}
	if legacyErr != nil && !errors.Is(legacyErr, ErrSagaNotFound) {
		return nil, legacyErr
	}

	return nil, ErrSagaNotFound
}

func (r *Router) getByRoute(ctx context.Context, route string, workflowID string) (*SagaStatus, error) {
	switch route {
	case RouteTemporal:
		return r.temporal.GetSagaStatus(ctx, workflowID)
	case RouteLegacy:
		fallthrough
	default:
		return r.legacy.GetSagaStatus(ctx, workflowID)
	}
}

func NeedsLegacyEventLoop(mode string, canaryPercent int) bool {
	resolver := NewRouteResolver(mode, canaryPercent)
	switch resolver.Mode() {
	case RouteLegacy, RouteCanary:
		return true
	default:
		return false
	}
}
