package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/redis/go-redis/v9"
	"go.temporal.io/sdk/client"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"

	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/engine"
	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/orchestration"
	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/service"
	temporalworker "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/temporal/worker"
	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
)

type appConfig struct {
	RuntimeMode string

	GrpcPort   string
	HealthPort string

	RedisHost string
	RedisPort string
	RedisPass string

	KafkaBrokers string
	CommandTopic string
	EventTopic   string

	RouteMode      string
	CanaryPercent  int
	LegacyLoopMode string

	TemporalAddress   string
	TemporalNamespace string
	TemporalTaskQueue string
}

func main() {
	cfg := loadConfig()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errCh := make(chan error, 4)
	var shutdownFns []func(context.Context)
	var mu sync.Mutex
	registerShutdown := func(fn func(context.Context)) {
		mu.Lock()
		defer mu.Unlock()
		shutdownFns = append(shutdownFns, fn)
	}

	if modeEnabled(cfg.RuntimeMode, "api") {
		apiCleanup, err := startAPIServer(ctx, cfg, errCh)
		if err != nil {
			log.Fatalf("failed to start API mode: %v", err)
		}
		registerShutdown(apiCleanup)
	}

	if modeEnabled(cfg.RuntimeMode, "worker") {
		workerCleanup, err := startTemporalWorker(ctx, cfg, errCh)
		if err != nil {
			log.Fatalf("failed to start worker mode: %v", err)
		}
		registerShutdown(workerCleanup)
	}

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)

	select {
	case <-quit:
		log.Printf("Received shutdown signal")
	case err := <-errCh:
		if err != nil {
			log.Printf("Runtime error: %v", err)
		}
	}

	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	mu.Lock()
	for i := len(shutdownFns) - 1; i >= 0; i-- {
		shutdownFns[i](shutdownCtx)
	}
	mu.Unlock()

	log.Printf("Saga orchestrator shutdown complete")
}

func loadConfig() appConfig {
	return appConfig{
		RuntimeMode: envOrDefault("SAGA_RUNTIME_MODE", "api"),
		GrpcPort:    envOrDefault("SAGA_GRPC_PORT", "50054"),
		HealthPort:  envOrDefault("SAGA_HEALTH_PORT", "8081"),

		RedisHost: envOrDefault("REDIS_HOST", "redis"),
		RedisPort: envOrDefault("REDIS_PORT", "6379"),
		RedisPass: strings.TrimSpace(os.Getenv("REDIS_PASSWORD")),

		KafkaBrokers: envOrDefault("KAFKA_BROKERS", "kafka:29092"),
		CommandTopic: envOrDefault("SAGA_COMMAND_TOPIC", "saga-commands"),
		EventTopic:   envOrDefault("SAGA_EVENT_TOPIC", "saga-events"),

		RouteMode:      envOrDefault("SAGA_ROUTE_ORDER_FULFILLMENT", orchestration.RouteLegacy),
		CanaryPercent:  envAsInt("SAGA_CANARY_PERCENT", 0),
		LegacyLoopMode: envOrDefault("SAGA_LEGACY_EVENT_LOOP", "auto"),

		TemporalAddress:   envOrDefault("TEMPORAL_ADDRESS", "temporal:7233"),
		TemporalNamespace: envOrDefault("TEMPORAL_NAMESPACE", "default"),
		TemporalTaskQueue: envOrDefault("TEMPORAL_TASK_QUEUE_ORDER", "saga.order.fulfillment"),
	}
}

func startAPIServer(ctx context.Context, cfg appConfig, errCh chan<- error) (func(context.Context), error) {
	log.Printf("Starting Saga API mode on gRPC :%s", cfg.GrpcPort)

	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPass,
		DB:       0,
	})

	legacyProducer, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers": cfg.KafkaBrokers,
	})
	if err != nil {
		rdb.Close()
		return nil, fmt.Errorf("create legacy kafka producer: %w", err)
	}

	legacyConsumer, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": cfg.KafkaBrokers,
		"group.id":          envOrDefault("SAGA_LEGACY_CONSUMER_GROUP", "saga-orchestrator-group"),
		"auto.offset.reset": "earliest",
	})
	if err != nil {
		legacyProducer.Close()
		rdb.Close()
		return nil, fmt.Errorf("create legacy kafka consumer: %w", err)
	}

	legacyEngine := engine.NewSagaEngine(rdb, legacyProducer, legacyConsumer, cfg.CommandTopic, cfg.EventTopic)
	legacyAdapter := orchestration.NewLegacyAdapter(legacyEngine)

	var temporalClient client.Client
	var temporalBackend orchestration.Backend = orchestration.NewUnavailableBackend("temporal", fmt.Errorf("temporal backend is not configured"))
	if strings.ToLower(strings.TrimSpace(cfg.RouteMode)) != orchestration.RouteLegacy {
		temporalClient, err = client.Dial(client.Options{
			HostPort:  cfg.TemporalAddress,
			Namespace: cfg.TemporalNamespace,
		})
		if err != nil {
			legacyConsumer.Close()
			legacyProducer.Close()
			rdb.Close()
			return nil, fmt.Errorf("dial temporal for API mode: %w", err)
		}
		temporalBackend = orchestration.NewTemporalAdapter(temporalClient, cfg.TemporalTaskQueue)
	} else {
		log.Printf("Saga API mode running with legacy route only")
	}

	resolver := orchestration.NewRouteResolver(cfg.RouteMode, cfg.CanaryPercent)
	routeStore := orchestration.NewRedisRouteStore(rdb, 7*24*time.Hour)
	router := orchestration.NewRouter(legacyAdapter, temporalBackend, resolver, routeStore)

	if shouldRunLegacyLoop(cfg) {
		go legacyAdapter.StartEventLoop(ctx)
		log.Printf("Legacy saga event loop enabled (topic=%s)", cfg.EventTopic)
	} else {
		log.Printf("Legacy saga event loop disabled")
	}

	lis, err := net.Listen("tcp", ":"+cfg.GrpcPort)
	if err != nil {
		if temporalClient != nil {
			temporalClient.Close()
		}
		legacyConsumer.Close()
		legacyProducer.Close()
		rdb.Close()
		return nil, fmt.Errorf("listen grpc: %w", err)
	}

	grpcServer := grpc.NewServer()
	sagav1.RegisterSagaServiceServer(grpcServer, service.NewSagaService(router))
	reflection.Register(grpcServer)

	go func() {
		log.Printf("Saga Orchestrator gRPC listening on %s", lis.Addr())
		if serveErr := grpcServer.Serve(lis); serveErr != nil {
			select {
			case errCh <- fmt.Errorf("saga grpc server failed: %w", serveErr):
			default:
			}
		}
	}()

	healthSrv := &http.Server{
		Addr: ":" + cfg.HealthPort,
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"healthy"}`))
		}),
	}
	go func() {
		log.Printf("Saga Orchestrator health server listening on :%s", cfg.HealthPort)
		if serveErr := healthSrv.ListenAndServe(); serveErr != nil && serveErr != http.ErrServerClosed {
			select {
			case errCh <- fmt.Errorf("saga health server failed: %w", serveErr):
			default:
			}
		}
	}()

	cleanup := func(shutdownCtx context.Context) {
		grpcServer.GracefulStop()
		_ = healthSrv.Shutdown(shutdownCtx)
		if temporalClient != nil {
			temporalClient.Close()
		}
		legacyConsumer.Close()
		legacyProducer.Close()
		rdb.Close()
	}
	return cleanup, nil
}

func startTemporalWorker(ctx context.Context, cfg appConfig, errCh chan<- error) (func(context.Context), error) {
	log.Printf("Starting Temporal worker mode (taskQueue=%s)", cfg.TemporalTaskQueue)

	temporalClient, err := client.Dial(client.Options{
		HostPort:  cfg.TemporalAddress,
		Namespace: cfg.TemporalNamespace,
	})
	if err != nil {
		return nil, fmt.Errorf("dial temporal for worker mode: %w", err)
	}

	gatewayCfg := temporalworker.DefaultGatewayConfig(cfg.KafkaBrokers)
	gatewayCfg.CommandTopic = cfg.CommandTopic
	gatewayCfg.EventTopic = cfg.EventTopic

	runner, err := temporalworker.NewRunner(ctx, temporalClient, temporalworker.RunnerConfig{TaskQueue: cfg.TemporalTaskQueue}, gatewayCfg)
	if err != nil {
		temporalClient.Close()
		return nil, fmt.Errorf("create temporal runner: %w", err)
	}

	go func() {
		if runErr := runner.Run(ctx); runErr != nil {
			select {
			case errCh <- runErr:
			default:
			}
		}
	}()

	cleanup := func(_ context.Context) {
		temporalClient.Close()
	}
	return cleanup, nil
}

func shouldRunLegacyLoop(cfg appConfig) bool {
	mode := strings.ToLower(strings.TrimSpace(cfg.LegacyLoopMode))
	switch mode {
	case "enabled", "true", "1", "on":
		return true
	case "disabled", "false", "0", "off":
		return false
	default:
		return orchestration.NeedsLegacyEventLoop(cfg.RouteMode, cfg.CanaryPercent)
	}
}

func modeEnabled(runtimeMode string, target string) bool {
	mode := strings.ToLower(strings.TrimSpace(runtimeMode))
	t := strings.ToLower(strings.TrimSpace(target))
	switch mode {
	case "all":
		return true
	case "api":
		return t == "api"
	case "worker":
		return t == "worker"
	default:
		return t == "api"
	}
}

func envOrDefault(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func envAsInt(key string, fallback int) int {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}
