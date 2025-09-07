# SportMetrics Automation Flow

1. New session `.json` file appears in `./sessions/`
2. Watcher script detects new file
3. Watcher script creates tasks for ALL configured stats by inserting entries into separate per-stat queue files
4. Queue worker polls all stat queues for pending tasks (round-robin)
5. Queue worker executes the proper session processor for each task
6. Queue worker updates task status in respective stat queue upon completion

## Watcher Script

**Purpose:** Monitor `./sessions/` for new `.json` files

- **Responsibility:** Create tasks for ALL configured stats by inserting entries into separate per-stat queue files
- **Technology:** Uses filesystem events (watchdog) for efficient monitoring
- **Features:**
  - Handles file write completion detection
  - Generates tasks across all active stat queues

## Queue Worker - Single Worker Architecture

**Architecture:** One worker process that polls ALL stat queues in round-robin fashion

- **Responsibility:** Poll all stat queues for pending tasks, execute appropriate processor class, update task status
- **Processing:** Round-robin across stat queues (running → cycling → all_sessions → repeat)
- **Future design:** Calls different processor classes based on stat type (not just different parameters)
- **Error handling:** Handles retry logic and error reporting across all queues
- **Updates:** Individual stat queue files
- **Benefits:** Simpler to implement and manage than multiple workers

## Queue Structure - Per-Stat Queues

```
bankend/automation/queues/
├── running_queue.json       # Queue for running stats
├── cycling_queue.json       # Queue for cycling stats  
├── all_sessions_queue.json  # Queue for comprehensive stats
└── queue_index.json         # Master index of all active queues
```

- Each queue file stores tasks with parameters and status for that specific stat type

## Future Processor Architecture - Processor Per Stat

**Current State:** One `session_processor.py` with all logic embedded

**Future Vision:** Extract dynamic parts from current processor into specialized classes

### Common Skeleton
Keep core logic:
- File loading
- Progress tracking
- Chart export
- etc.

### Extracted Dynamic Parts
- Filtering logic
- Data mapping
- Chart configuration

### Processor Classes
- `RunningProcessor` - Inherits skeleton + running-specific filters/mapping
- `CyclingProcessor` - Inherits skeleton + cycling-specific filters/mapping  
- `AllSessionsProcessor` - Inherits skeleton + comprehensive filters/mapping
- `CustomProcessor` - Inherits skeleton + user-defined filters/mapping

### Refactoring Strategy
- Keep `SessionProcessor` base class with proven Chart.js export, file handling, progress tracking
- Extract `should_include_session()`, `extract_metrics()`, and export config as overridable methods
- Each stat processor overrides filtering and data mapping logic

### Benefits
- Reuse proven code
- Specialized logic per stat
- Maintainable architecture

---

## Phase 1: Core Infrastructure

### 1. ✅ Design queue system architecture and data structures - COMPLETED
- ✅ Define per-stat queue JSON schema (task_id, session_file, status, timestamps)
- ✅ Plan task status lifecycle (pending → processing → completed/failed)  
- ✅ Design retry mechanism and error tracking
- ✅ Design queue_index.json for managing multiple stat queues
- ✅ Architecture: separate queue file per stat type for isolation and scalability

### 2. ✅ Create file watcher script for sessions directory - COMPLETED
- ✅ Monitor `./sessions/` for new `.json` files (using directory polling)
- ✅ Handle file write completion detection (stability check)
- ✅ Deduplication to avoid processing same file multiple times (last processed file tracking)
- ✅ Configurable state file location for deployment flexibility

### 2.5. ✅ Integrate file watcher with queue system - COMPLETED
- ✅ Generate tasks for ALL active stat queues when new session detected
- ✅ Batch processing support for multiple files
- ✅ Connect file watcher to queue management system

### 3. ✅ Implement queue management system with JSON storage - COMPLETED
- ✅ Create per-stat queue files with atomic read/write operations
- ✅ Add file locking for concurrent access safety across multiple queue files
- ✅ Implement `queue_index.json` for tracking all active stat queues
- ✅ Queue persistence and recovery for each stat queue
- ✅ Operations: `add_task_to_stat()`, `get_next_task_from_stat()`, `complete_task()`

## Phase 2: Processing Engine

### 4. ✅ Build SINGLE stat factory queue worker - COMPLETED
- ✅ ONE worker process that polls ALL stat queues for pending tasks (round-robin)
- ✅ **Phase 1:** Execute current `session_processor.py` with different parameters per stat
- **Future:** Execute different processor classes based on stat type (RunningProcessor, CyclingProcessor, etc.)
- ✅ Update task status in respective stat queue upon completion
- ✅ Process one task at a time across all queues (no concurrent processing initially)
- ✅ Design worker to easily support future processor-per-stat architecture

### 5. ✅ Add queue operations for per-stat architecture - COMPLETED
- ✅ `add_task_to_stat(stat_id, session_file)` - Add task to specific stat queue
- ✅ `get_next_task_from_stat(stat_id)` - Get pending task from specific stat queue
- ✅ `complete_task(stat_id, task_id)` - Mark task as completed in specific queue
- ✅ `retry_task(stat_id, task_id)` - Handle failed task retry in specific queue
- ✅ `list_active_stats()` - Get all active stat queue IDs
- ✅ `get_all_queue_stats()` - Aggregate stats across all queues

### 6. Create chart generation tasks configuration
- Define default stat configs (all sessions, by sport, distance ranges)
- Support custom stat definitions  
- Each stat config defines: output file, filters, priority
- **Note:** Stat config will be handled later - focus on queue mechanics first

## Phase 3: Reliability & Operations

### 7. Implement error handling and retry logic
- Retry failed tasks with backoff strategy
- Dead letter queue for permanently failed tasks
- Error categorization (temporary vs permanent failures)

### 8. Add logging and monitoring for automation
- Structured logging for file events and processing
- Queue metrics (pending, processing, completed, failed)
- Performance monitoring (processing times, throughput)

### 8.5. Admin Web UI for Queue Management
- **Admin API Server (Flask)**
  - REST API endpoints for queue data (`/api/queues`, `/api/queues/{id}/tasks`)
  - Task management operations (change status, retry failed tasks)
  - Configuration view (`/api/config`)
  - Health check endpoint (`/api/health`)
  - CORS enabled for frontend access

- **Admin Web Interface**
  - Queue overview dashboard (all queues with task counts)
  - Task list view per queue with filtering/sorting
  - Task detail view with full metadata
  - Task status management (manual status changes)
  - Task retry functionality for failed tasks
  - Real-time updates (polling or WebSocket)

- **Task Process Logging (Future)**
  - Capture stdout/stderr from session_processor.py execution
  - Store task execution logs with timestamps
  - Log viewing interface in admin UI
  - Log retention and cleanup policies
  - Structured logging with correlation IDs

- **Docker Integration**
  - Admin API service in Docker compose
  - Admin UI served via nginx
  - Proper networking between services
  - Volume mounting for queue data access

- **Features**
  - View all queues and their statistics
  - List tasks with status, timestamps, error messages
  - Change task status (pending/processing/completed/failed)
  - Retry failed tasks
  - View task execution details
  - Monitor queue health and performance
  - Create new tasks manually (testing/debugging)

## Phase 4: Integration

### 9. ✅ Create service management integration - COMPLETED
- ✅ Add automation commands to `manage.sh`
- ✅ Docker integration for containerized processing
- Systemd/supervisor integration for production

### 10. ✅ Add configuration file for automation settings - COMPLETED
- ✅ Chart generation rules and filters (JSON-based configuration)
- ✅ Processing intervals and batch sizes
- ✅ Error handling and retry policies
- ✅ Monitoring and alerting settings

### 10.5. ✅ Configure nginx to serve JSON data from separate directory - COMPLETED
- ✅ Create custom nginx configuration with `/data/` endpoint
- ✅ Configure nginx to serve JSON files from `/app/data/` directory
- ✅ Add CORS headers for frontend access
- ✅ Add security restrictions (JSON files only)
- ✅ Update Docker compose with custom nginx config and data volume

## Phase 5: Processor Refactoring (Future)

### 11. Refactor current session_processor.py into base class + specialized processors

#### Extract SessionProcessor base class (skeleton) with core functionality:
- File loading (`load_session()`)
- Progress tracking (tqdm integration)
- Chart.js export (`export_to_chartjs()`)
- Chart registration (`register_chart()`)

#### Make dynamic parts overridable:
- `should_include_session()` - filtering logic per stat type
- `extract_metrics()` - data mapping per stat type  
- `get_chart_config()` - chart configuration per stat type

#### Create specialized processor classes:
- `RunningProcessor(SessionProcessor)` - running-specific logic
- `CyclingProcessor(SessionProcessor)` - cycling-specific logic
- `AllSessionsProcessor(SessionProcessor)` - comprehensive logic

#### Update worker to instantiate appropriate processor class per stat queue
