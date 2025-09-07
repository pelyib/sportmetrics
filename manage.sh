#!/bin/bash

# SportMetrics Service Manager
# Unified script to manage web server and processor services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_NAME=$(basename "$0")

# Show usage
show_usage() {
    echo -e "${BLUE}SportMetrics Service Manager${NC}"
    echo ""
    echo "Usage: $SCRIPT_NAME <command> [options]"
    echo ""
    echo "Commands:"
    echo "  web start       - Start web server"
    echo "  web stop        - Stop web server"
    echo "  web restart     - Restart web server"
    echo "  web status      - Show web server status"
    echo ""
    echo "  automation start - Start automation (file watcher + queue worker)"
    echo "  automation stop  - Stop automation"
    echo "  automation restart - Restart automation"
    echo "  automation status  - Show automation status"
    echo "  automation logs    - Show automation logs"
    echo ""
    echo "  process <args>  - Run processor with arguments"
    echo ""
    echo "Examples:"
    echo "  $SCRIPT_NAME web start"
    echo "  $SCRIPT_NAME automation start"
    echo "  $SCRIPT_NAME process --sport RUNNING --output running.json"
    echo "  $SCRIPT_NAME process --help"
    echo ""
    exit 1
}

# Web server management
manage_web() {
    local action=$1
    
    case $action in
        start)
            echo -e "${YELLOW}🌐 Starting web server...${NC}"
            docker-compose --profile web up -d
            
            echo ""
            echo -e "${GREEN}🎉 Web server is running!${NC}"
            echo ""
            echo -e "${BLUE}📊 Access at: http://localhost:8080${NC}"
            
            # Show available data files
            if ls backend/output/*.json >/dev/null 2>&1; then
                echo ""
                echo -e "${BLUE}💡 Available data files:${NC}"
                for file in backend/output/*.json; do
                    filename=$(basename "$file")
                    echo "  http://localhost:8080?data=data/$filename"
                done
            fi
            ;;
            
        stop)
            echo -e "${YELLOW}🛑 Stopping web server...${NC}"
            docker-compose --profile web down
            echo -e "${GREEN}✅ Web server stopped${NC}"
            ;;
            
        restart)
            echo -e "${YELLOW}🔄 Restarting web server...${NC}"
            docker-compose --profile web down
            docker-compose --profile web up -d
            echo -e "${GREEN}✅ Web server restarted${NC}"
            echo -e "${BLUE}📊 Access at: http://localhost:8080${NC}"
            ;;
            
        status)
            echo -e "${BLUE}📋 Web server status:${NC}"
            if docker-compose --profile web ps | grep -q "polar-web"; then
                docker-compose --profile web ps
                echo ""
                echo -e "${GREEN}✅ Web server is running at http://localhost:8080${NC}"
            else
                echo -e "${RED}❌ Web server is not running${NC}"
            fi
            ;;
            
        *)
            echo -e "${RED}❌ Unknown web command: $action${NC}"
            echo "Available: start, stop, restart, status"
            exit 1
            ;;
    esac
}

# Automation service management
manage_automation() {
    local action=$1
    
    case $action in
        start)
            echo -e "${YELLOW}🤖 Starting automation services...${NC}"
            docker-compose --profile automation up -d
            
            echo ""
            echo -e "${GREEN}🎉 Automation services are running!${NC}"
            echo -e "${BLUE}📁 Monitoring: ./sessions${NC}"
            echo -e "${BLUE}📊 Output: ./frontend/public/data${NC}"
            
            # Show queue status after a moment
            sleep 2
            echo ""
            echo -e "${BLUE}📋 Queue status:${NC}"
            docker-compose --profile automation exec automation ls -la /app/queues/ 2>/dev/null || echo "  Queues initializing..."
            ;;
            
        stop)
            echo -e "${YELLOW}🛑 Stopping automation services...${NC}"
            docker-compose --profile automation down
            echo -e "${GREEN}✅ Automation services stopped${NC}"
            ;;
            
        restart)
            echo -e "${YELLOW}🔄 Restarting automation services...${NC}"
            docker-compose --profile automation down
            docker-compose --profile automation up -d
            echo -e "${GREEN}✅ Automation services restarted${NC}"
            ;;
            
        status)
            echo -e "${BLUE}📋 Automation services status:${NC}"
            if docker-compose --profile automation ps | grep -q "polar-automation"; then
                docker-compose --profile automation ps
                echo ""
                echo -e "${GREEN}✅ Automation services are running${NC}"
                
                # Show queue stats if possible
                echo ""
                echo -e "${BLUE}📊 Queue directories:${NC}"
                docker-compose --profile automation exec automation ls -la /app/queues/ 2>/dev/null || echo "  Cannot access queue info"
            else
                echo -e "${RED}❌ Automation services are not running${NC}"
            fi
            ;;
            
        logs)
            echo -e "${BLUE}📋 Automation services logs:${NC}"
            docker-compose --profile automation logs -f automation
            ;;
            
        *)
            echo -e "${RED}❌ Unknown automation command: $action${NC}"
            echo "Available: start, stop, restart, status, logs"
            exit 1
            ;;
    esac
}

manage_process() {
    shift # Remove 'process' from args
    echo -e "${YELLOW}📊 Running processor...${NC}"
    docker-compose --profile process run --rm processor "$@"
    echo -e "${GREEN}✅ Processing complete!${NC}"
}

# Main logic
if [ $# -eq 0 ]; then
    show_usage
fi

COMMAND=$1

case $COMMAND in
    web)
        if [ $# -lt 2 ]; then
            echo -e "${RED}❌ Web command requires an action${NC}"
            show_usage
        fi
        manage_web "$2"
        ;;
        
    automation)
        if [ $# -lt 2 ]; then
            echo -e "${RED}❌ Automation command requires an action${NC}"
            show_usage
        fi
        manage_automation "$2"
        ;;
        
    process)
        manage_process "$@"
        ;;
        
    help|--help|-h)
        show_usage
        ;;
        
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        show_usage
        ;;
esac
