package models

import (
	"time"
)

type Outbox struct {
	ID            uint      `gorm:"primaryKey"`
	AggregateType string    `gorm:"index"`
	AggregateID   string    `gorm:"index"`
	EventType     string
	Payload       []byte    `gorm:"type:bytea"` // Binary payload (Protobuf)
	CreatedAt     time.Time `gorm:"index"`
}
