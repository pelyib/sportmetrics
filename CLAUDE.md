# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SportMetrics is a Docker-based analytics platform that transforms fitness training session data into interactive Chart.js visualizations. The system processes JSON session files from fitness devices (Polar format) and generates web-accessible charts with filtering capabilities.

## Key Commands

### Build and Docker Management
```bash
# Build the processor image
make build

# Force rebuild without cache
make build-force

# Clean up images
make clean
```

### Service Management
```bash
# Web server (serves frontend on port 13000)
./manage.sh web start|stop|restart|status

# Automation services (file watching + queue processing)
./manage.sh automation start|stop|restart|status|logs

# One-off data processing
./manage.sh process [options]
```

### Data Processing Examples
```bash
# Process all running sessions
./manage.sh process --sport RUNNING --output /app/output/running.json

# Process long distance sessions (20km+)
./manage.sh process --min-distance 20000 --output /app/output/long-runs.json

# Process with date range
./manage.sh process --start-date 2024-01-01 --end-date 2024-12-31

# Show all processor options
./manage.sh process --help
```

## Architecture Overview

### Data Flow
1. **Input**: Session JSON files → `./sessions/` directory
2. **Processing**: `backend/src/session_processor.py` extracts autolap data
3. **Output**: Chart.js JSON files → `frontend/public/data/`
4. **Registry**: Charts auto-register in `charts.json` with metadata
5. **Frontend**: Dynamic navbar loads from `charts.json`, serves visualizations

### Core Components

**Backend Processing (`backend/src/`)**
- `session_processor.py`: Main processor with filtering and Chart.js export
- `automation/`: File watcher system with queue-based processing
  - `file_watcher.py`: Monitors sessions directory for new files
  - `queue_manager.py`: Manages processing queues by sport/type
  - `queue_worker.py`: Processes queued tasks
  - `automation_config.json`: Configuration for automation services

**Frontend (`frontend/public/`)**
- `index.html`: Main interface with controls and chart canvas
- `js/chart.js`: Chart.js integration, filtering, custom legend
- `css/styles.css`: Responsive styling
- `data/charts.json`: Chart registry with metadata and navigation

**Docker Services**
- `automation`: File watcher + queue worker for automatic processing
- `processor`: Manual processing service for one-off runs
- `web`: Nginx serving frontend with data file access

### Processing Filters
The session processor supports comprehensive filtering:
- `--sport`: Filter by sport type (RUNNING, CYCLING, etc.)
- `--start-date`/`--end-date`: Date range filtering
- `--min-duration`: Minimum session duration in seconds
- `--min-distance`: Minimum distance in meters
- `--min-calories`: Minimum calories burned

### Chart Registration System
Charts automatically register in `charts.json` with:
- Auto-generated metadata (session count, date ranges, sports)
- Tag-based organization (running, cycling, endurance, distance)
- Dynamic frontend navigation integration

## Development Patterns

### Adding New Processing Logic
1. Extend `SessionProcessor.process_sessions()` for new data extraction
2. Update `export_to_chartjs()` for new chart types
3. Charts auto-register with appropriate tags and metadata

### Frontend Customization
- Chart configurations in `js/chart.js` follow Chart.js patterns
- Filter system is extensible (search, distance range, sport-based)
- Custom legend system integrates with Chart.js datasets

### Docker Profiles
- Use `--profile web` for frontend development
- Use `--profile automation` for testing file watching
- Use `--profile process` for data processing tasks

## File Structure
```
sessions/                     # Input JSON files from fitness devices
backend/
  src/
    session_processor.py      # Core processing logic
    automation/               # Automated processing system
docker/
  backend/data/               # Persistent automation data
  frontend/data/charts/       # Generated chart files
frontend/public/              # Static web assets
  data/                       # Chart data and registry
```

## Port Configuration
- Web interface: http://localhost:13000
- Data access: Charts served from `/app/data` in nginx container

## Key Data Formats
- Input: Polar training session JSON with exercises and autoLaps
- Output: Chart.js line chart configurations with autolap timing data
- Registry: `charts.json` with chart metadata and navigation structure