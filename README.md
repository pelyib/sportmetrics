# SportMetrics

**A flexible analytics platform for sports and fitness data visualization**

SportMetrics transforms your training session data into interactive, filterable charts and insights. Built with a modular architecture to support multiple data sources and visualization types.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Fitness session JSON files in `./sessions/` directory

### Build and Run
```bash
# Build the application
make build

# Process sessions and generate charts
./manage.sh process --sport RUNNING --output /app/output/running.json

# Start web server
./manage.sh web start

# Access at http://localhost:13000
```

### Service Management
```bash
# Web server controls
./manage.sh web start     # Start web server
./manage.sh web stop      # Stop web server  
./manage.sh web status    # Check status
./manage.sh web restart   # Restart web server

# Data processing
./manage.sh process --help                    # Show processing options
./manage.sh process --sport CYCLING          # Process cycling sessions
./manage.sh process --min-distance 20000     # Long distance sessions
```

## 📊 Key Features

### 🔄 Dynamic Chart Discovery
- **Auto-registration**: Charts automatically register in `charts.json` when generated
- **Dynamic navbar**: Web interface loads available charts dynamically
- **Tag-based organization**: Charts organized by sport, distance, activity type
- **Metadata tracking**: Session count, date ranges, sports, distance ranges

### 🏃 Multi-Sport Analytics
- Supports running, cycling, and other fitness activities
- Sport-specific filtering and visualization
- Metadata extraction (distance, duration, sport, ascent)
- Autolap timing analysis

### 🔍 Advanced Filtering
- **Search**: Find sessions by name/date
- **Distance range**: Dual-range slider for distance filtering
- **Sport filtering**: Multi-sport data organization
- **Reset functionality**: Quick filter reset

### 📱 Modern Interface
- **Responsive design**: Works on desktop and mobile
- **Interactive charts**: Chart.js powered visualizations  
- **Loading states**: Clean loading without layout glitches
- **Custom legends**: Enhanced session management

## 🛠️ Development

### Frontend Architecture
- `frontend/public/index.html` - Main HTML structure
- `frontend/public/css/styles.css` - Responsive styling
- `frontend/public/js/chart.js` - Chart logic and interactivity
- `frontend/public/data/charts.json` - Chart configuration registry

### Backend Processing
- `backend/src/session_processor.py` - Session processing and Chart.js export
- Automatic chart registration with metadata extraction
- Data flows: `./sessions/*.json` → processing → `frontend/public/data/*.json`

### Docker Services
- **processor**: Python backend for session processing
- **web**: Nginx serving frontend with data access
- Volume mounting for data persistence

## 📈 Usage Examples

```bash
# Process all running sessions with distance filter
./manage.sh process --sport RUNNING --min-distance 20000 --output /app/output/long-runs.json

# Process cycling sessions from specific date range  
./manage.sh process --sport CYCLING --start-date 2024-01-01 --min-distance 15000

# Process all sessions for comprehensive overview
./manage.sh process --output /app/output/all-sessions.json

# Force rebuild image with latest code changes
make build-force
```

## ⚙️ Configuration Options

### Session Processing Filters
- `--sport`: Filter by sport type (RUNNING, CYCLING, etc.)
- `--start-date` / `--end-date`: Date range (YYYY-MM-DD)
- `--min-duration`: Minimum duration in seconds
- `--min-distance`: Minimum distance in meters  
- `--min-calories`: Minimum calories burned
- `--output`: Output file path (within container: `/app/output/filename.json`)

### Chart Configuration (`charts.json`)
- **Automatic registration**: Charts register when processed
- **Metadata tracking**: Session counts, date ranges, sports
- **Tag system**: Flexible organization (running, endurance, distance, etc.)
- **Default chart**: Configurable landing page chart

## 🐳 Docker Management

```bash
# Build management
make build              # Build image
make build-force        # Force rebuild (no cache)
make clean             # Remove images

# Service management  
./manage.sh web start   # Start web interface
./manage.sh web stop    # Stop services
./manage.sh process     # Run data processing

# Direct docker-compose (advanced)
docker-compose --profile web up -d
docker-compose --profile process run --rm processor --help
```

## 🎯 Extensibility

### Adding New Chart Types
1. Extend `session_processor.py` with new export methods
2. Charts auto-register with appropriate tags and metadata
3. Frontend dynamically loads new chart types

### Custom Data Sources
- Modular processor design supports different input formats
- Easy to extend beyond fitness data to other analytics
- Tag system supports arbitrary categorization

### Filter Extensions
- Current: search, distance range, sport filtering
- Extensible to: time-based, performance metrics, custom attributes
- Frontend filter system designed for easy expansion

## 📝 Output Format

SportMetrics generates Chart.js-compatible JSON files with:
- Interactive line chart configurations
- Dataset per session with timing data
- Rich metadata for filtering and organization  
- Responsive chart options optimized for web display
- Custom legend integration for enhanced UX

---

*SportMetrics: Transform your training data into actionable insights* 🏃📊
