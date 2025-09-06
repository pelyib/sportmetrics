# SportMetrics - Docker Build Management

.PHONY: help build build-force clean

# Default target
help: ## Show available build targets
	@echo "SportMetrics - Docker Build Management"
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the SportMetrics Docker image
	@echo "🏗️  Building SportMetrics image..."
	docker build -f docker/backend/Dockerfile -t polar-processor .
	@echo "✅ Image built successfully"

build-force: ## Force rebuild (no cache)
	@echo "🏗️  Force building SportMetrics image..."
	docker build --no-cache -f docker/backend/Dockerfile -t polar-processor .
	@echo "✅ Image built successfully"

clean: ## Remove SportMetrics image
	@echo "🧹 Cleaning up SportMetrics image..."
	-docker rmi polar-processor 2>/dev/null || true
	@echo "✅ Cleanup complete"
