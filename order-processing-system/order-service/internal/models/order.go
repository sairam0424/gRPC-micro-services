package models

import (
	"time"
)

type Order struct {
	OrderID    string      `gorm:"primaryKey"`
	CustomerID string      `gorm:"index"`
	Status     string      `gorm:"type:string"`
	CreatedAt  time.Time
	UpdatedAt  time.Time
	Items      []OrderItem `gorm:"foreignKey:OrderID"`
}

type OrderItem struct {
	ID         uint   `gorm:"primaryKey"`
	OrderID    string `gorm:"index"`
	ProductID  string
	Quantity   uint32
	PriceCents int64
}
