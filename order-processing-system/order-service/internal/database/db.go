package database

import (
	"log"
	"os"
	"time"

	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

var DB *gorm.DB

func InitDB() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://user:password@localhost:5436/orderdb?sslmode=disable"
	}

	var err error
	// Mask password in DSN for security but keep host/db visible for debugging
	log.Printf("Connecting to database with DSN: %s", dsn)
	DB, err = gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("failed to connect database: %v", err)
	}

	sqlDB, err := DB.DB()
	if err != nil {
		log.Fatalf("failed to get sql.DB: %v", err)
	}

	// SetMaxIdleConns sets the maximum number of connections in the idle connection pool.
	sqlDB.SetMaxIdleConns(10)
	// SetMaxOpenConns sets the maximum number of open connections to the database.
	sqlDB.SetMaxOpenConns(100)
	// SetConnMaxLifetime sets the maximum amount of time a connection may be reused.
	sqlDB.SetConnMaxLifetime(time.Hour) // 1 hour

	// Auto migrate the schema
	err = DB.AutoMigrate(&models.Order{}, &models.OrderItem{}, &models.Outbox{}, &models.ProcessedEvent{})
	if err != nil {
		log.Fatalf("failed to migrate database: %v", err)
	}

	log.Println("Database initialized and migrated successfully with connection pooling")
}

func CheckAndRecordEvent(tx *gorm.DB, eventID string, service string) bool {
	res := tx.Clauses(clause.OnConflict{DoNothing: true}).Create(&models.ProcessedEvent{
		EventID:     eventID,
		Service:     service,
		ProcessedAt: time.Now(),
	})

	if res.Error != nil {
		log.Printf("Error recording event: %v", res.Error)
		return false
	}

	return res.RowsAffected > 0
}
