package models

import (
	"time"
)

type ProcessedEvent struct {
	EventID   string    `gorm:"primaryKey"`
	Service   string    `gorm:"primaryKey"`
	ProcessedAt time.Time
}
