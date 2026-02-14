package models

import (
	"time"
)

type Outbox struct {
	ID            uint      `gorm:"primaryKey"`
	AggregateType string    `gorm:"index"`
	AggregateID   string    `gorm:"index"`
	EventType     string
	Payload       string    `gorm:"type:text"` // JSON payload
	CreatedAt     time.Time `gorm:"index"`
}
