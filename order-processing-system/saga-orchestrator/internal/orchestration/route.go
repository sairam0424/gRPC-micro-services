package orchestration

import (
	"crypto/sha1"
	"encoding/binary"
	"fmt"
	"strings"
)

type RouteResolver struct {
	mode          string
	canaryPercent int
}

func NewRouteResolver(mode string, canaryPercent int) *RouteResolver {
	normalized := strings.ToLower(strings.TrimSpace(mode))
	switch normalized {
	case RouteLegacy, RouteTemporal, RouteCanary:
	default:
		normalized = RouteLegacy
	}

	if canaryPercent < 0 {
		canaryPercent = 0
	}
	if canaryPercent > 100 {
		canaryPercent = 100
	}

	return &RouteResolver{mode: normalized, canaryPercent: canaryPercent}
}

func (r *RouteResolver) Decide(orderID string) string {
	switch r.mode {
	case RouteLegacy:
		return RouteLegacy
	case RouteTemporal:
		return RouteTemporal
	case RouteCanary:
		if r.canaryPercent == 0 {
			return RouteLegacy
		}
		if r.canaryPercent == 100 {
			return RouteTemporal
		}
		bucket := hashBucket(orderID)
		if bucket < uint32(r.canaryPercent) {
			return RouteTemporal
		}
		return RouteLegacy
	default:
		return RouteLegacy
	}
}

func (r *RouteResolver) Mode() string {
	return r.mode
}

func hashBucket(value string) uint32 {
	sum := sha1.Sum([]byte(value))
	return binary.BigEndian.Uint32(sum[:4]) % 100
}

func NormalizeRoute(route string) (string, error) {
	r := strings.ToLower(strings.TrimSpace(route))
	switch r {
	case RouteLegacy, RouteTemporal:
		return r, nil
	default:
		return "", fmt.Errorf("invalid route %q", route)
	}
}
