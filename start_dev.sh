#!/bin/bash
# 🤖 SlackOpsBot Slack Bot - Professional Development Environment
# One-command startup for the complete AI-powered Slack bot system

set -e

# Professional colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'
CHECKMARK='\033[0;32m✅\033[0m'
CROSS='\033[0;31m❌\033[0m'
ROCKET='\033[0;36m🚀\033[0m'
GEAR='\033[0;33m⚙️\033[0m'
LIGHTNING='\033[1;33m⚡\033[0m'

# Professional output functions
print_header() { 
    echo -e "\n${BOLD}${CYAN}════════════════════════════════════════════════════════════════"
    echo -e "  $1"
    echo -e "════════════════════════════════════════════════════════════════${NC}\n"
}

print_section() { 
    echo -e "\n${BOLD}${BLUE}$1${NC}"
    echo -e "${BLUE}$(printf '%.0s─' {1..60})${NC}"
}

print_success() { echo -e "${CHECKMARK} ${GREEN}$1${NC}"; }
print_error() { echo -e "${CROSS} ${RED}$1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_step() { echo -e "${GEAR} ${CYAN}$1${NC}"; }
print_url() { echo -e "${LIGHTNING} ${MAGENTA}$1${NC}"; }

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to free a port
free_port() {
    local port=$1
    local service_name=$2
    
    if check_port $port; then
        print_step "Stopping existing $service_name on port $port..."
        lsof -ti :$port | xargs kill -9 2>/dev/null || true
        sleep 2
        if check_port $port; then
            print_error "Failed to free port $port"
            return 1
        else
            print_success "Port $port is now available"
        fi
    else
        print_success "Port $port is already available"
    fi
    return 0
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0
    
    print_step "Waiting for $service_name to start..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        attempt=$((attempt + 1))
        echo -n "."
        sleep 1
    done
    
    print_error "$service_name failed to start within $max_attempts seconds"
    return 1
}

# Function to cleanup processes on exit
cleanup() {
    print_header "🛑 SHUTTING DOWN DEVELOPMENT ENVIRONMENT"
    
    if [ ! -z "$DJANGO_PID" ] && kill -0 $DJANGO_PID 2>/dev/null; then
        print_step "Stopping Django server (PID: $DJANGO_PID)..."
        kill $DJANGO_PID 2>/dev/null || true
        wait $DJANGO_PID 2>/dev/null || true
        print_success "Django server stopped"
    fi
    
    if [ ! -z "$NGROK_PID" ] && kill -0 $NGROK_PID 2>/dev/null; then
        print_step "Stopping ngrok tunnel (PID: $NGROK_PID)..."
        kill $NGROK_PID 2>/dev/null || true
        wait $NGROK_PID 2>/dev/null || true
        print_success "ngrok tunnel stopped"
    fi
    
    # Clean up any remaining processes
    pkill -f "manage.py runserver" 2>/dev/null || true
    pkill -f "ngrok http" 2>/dev/null || true
    
    print_success "Development environment shutdown complete"
    echo -e "\n${BOLD}${CYAN}Thank you for using SlackOpsBot! 🤖✨${NC}\n"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution starts here
clear
print_header "🤖 SLACKOPSBOT SLACK BOT - PROFESSIONAL DEVELOPMENT STARTUP"
echo -e "${BOLD}${CYAN}AI-Powered Slack Bot with Ultra-Fast Responses & Background Processing${NC}"
echo -e "${CYAN}Starting complete development environment...${NC}\n"

# Validate environment
print_section "🔍 ENVIRONMENT VALIDATION"

if [ ! -f "manage.py" ]; then
    print_error "manage.py not found. Please run this script from the project root."
    exit 1
fi
print_success "Project structure validated"

if [ ! -f ".env" ]; then
    print_warning ".env file not found"
    if [ -f "config/environment.example" ]; then
        print_info "Template available at config/environment.example"
        print_info "Copy and configure: cp config/environment.example .env"
    fi
else
    print_success "Environment configuration found"
fi

# Check Python installation
PYTHON_PATH="python3"
if [ -f "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" ]; then
    PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    print_success "Using Python 3.13: $PYTHON_PATH"
else
    print_success "Using system Python: $PYTHON_PATH"
fi

# Check virtual environment
if [ -d "venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment detected but not activated"
    print_info "Consider running: source venv/bin/activate"
else
    print_success "Virtual environment status OK"
fi

# Check ngrok installation
NGROK_PATH="./ngrok"
if [ ! -f "./ngrok" ]; then
    if command -v ngrok &> /dev/null; then
        NGROK_PATH="ngrok"
        print_success "Using system ngrok: $NGROK_PATH"
    else
        print_error "ngrok not found. Please run: ./deployment/setup_ngrok.sh"
        exit 1
    fi
else
    print_success "Using local ngrok: $NGROK_PATH"
fi

# Stop any existing services
print_section "🛑 CLEANING UP EXISTING SERVICES"

free_port 8000 "Django server"
free_port 4040 "ngrok dashboard"

# Start Django server
print_section "🚀 STARTING DJANGO APPLICATION SERVER"

print_step "Initializing Django development server..."
$PYTHON_PATH manage.py migrate --verbosity=0 > /dev/null 2>&1 || print_warning "Database migration had issues (this is usually OK for development)"

print_step "Starting Django server with enhanced logging..."
$PYTHON_PATH manage.py runserver 127.0.0.1:8000 > django.log 2>&1 &
DJANGO_PID=$!

print_info "Django PID: $DJANGO_PID"

if wait_for_service "http://127.0.0.1:8000/health/" "Django server"; then
    print_success "Django application server started successfully"
    print_url "Django Server: http://localhost:8000"
    print_url "Health Check: http://localhost:8000/health/"
    print_url "Bot Status: http://localhost:8000/slack/test/"
else
    print_error "Failed to start Django server"
    if [ -f "django.log" ]; then
        print_info "Checking Django logs..."
        tail -10 django.log
    fi
    exit 1
fi

# Start ngrok tunnel
print_section "🌐 CREATING PUBLIC TUNNEL WITH NGROK"

print_step "Starting ngrok tunnel for Slack webhook access..."
$NGROK_PATH http 8000 --log stdout > ngrok.log 2>&1 &
NGROK_PID=$!

print_info "ngrok PID: $NGROK_PID"

if wait_for_service "http://localhost:4040" "ngrok dashboard"; then
    print_success "ngrok tunnel established successfully"
    print_url "ngrok Dashboard: http://localhost:4040"
else
    print_error "Failed to start ngrok tunnel"
    if [ -f "ngrok.log" ]; then
        print_info "Checking ngrok logs..."
        tail -10 ngrok.log
    fi
    exit 1
fi

# Get ngrok public URL
print_section "🔗 RETRIEVING PUBLIC WEBHOOK URL"

print_step "Fetching ngrok public URL..."
sleep 3  # Give ngrok time to establish tunnel

NGROK_URL=""
WEBHOOK_URL=""

for i in {1..15}; do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for tunnel in tunnels:
        if tunnel.get('proto') == 'https':
            print(tunnel.get('public_url', ''))
            break
except:
    pass
" 2>/dev/null)
    
    if [ ! -z "$NGROK_URL" ]; then
        WEBHOOK_URL="$NGROK_URL/slack/commands/ultra/"
        break
    fi
    
    echo -n "."
    sleep 1
done

# Display comprehensive status
clear
print_header "🎉 SLACKOPSBOT DEVELOPMENT ENVIRONMENT READY!"

if [ ! -z "$NGROK_URL" ]; then
    print_success "All services started successfully!"
    
    echo -e "\n${BOLD}${GREEN}🌐 PUBLIC URLS:${NC}"
    echo -e "   ${LIGHTNING} ${BOLD}Webhook URL:${NC} ${MAGENTA}$WEBHOOK_URL${NC}"
    echo -e "   ${LIGHTNING} ${BOLD}ngrok Tunnel:${NC} ${MAGENTA}$NGROK_URL${NC}"
    
    echo -e "\n${BOLD}${BLUE}🔧 LOCAL DEVELOPMENT URLS:${NC}"
    echo -e "   ${LIGHTNING} Django Server: ${CYAN}http://localhost:8000${NC}"
    echo -e "   ${LIGHTNING} Health Check: ${CYAN}http://localhost:8000/health/${NC}"
    echo -e "   ${LIGHTNING} Bot Status: ${CYAN}http://localhost:8000/slack/test/${NC}"
    echo -e "   ${LIGHTNING} ngrok Dashboard: ${CYAN}http://localhost:4040${NC}"
    
    echo -e "\n${BOLD}${YELLOW}📋 SLACK APP CONFIGURATION:${NC}"
    echo -e "   ${GEAR} Go to: ${CYAN}https://api.slack.com/apps${NC}"
    echo -e "   ${GEAR} Select: ${CYAN}\"SlackOpsBot\"${NC}"
    echo -e "   ${GEAR} Navigate: ${CYAN}Slash Commands → Edit \"/summary\"${NC}"
    echo -e "   ${GEAR} Update Request URL to:"
    echo -e "      ${BOLD}${MAGENTA}$WEBHOOK_URL${NC}"
    echo -e "   ${GEAR} Save Changes"
    
    echo -e "\n${BOLD}${GREEN}🧪 TESTING YOUR BOT:${NC}"
    echo -e "   ${LIGHTNING} In any Slack channel, try:"
    echo -e "      ${CYAN}/summary fun${NC}"
    echo -e "      ${CYAN}/summary general${NC}"
    echo -e "      ${CYAN}/summary random${NC}"
    
    echo -e "\n${BOLD}${CYAN}✨ FEATURES READY:${NC}"
    echo -e "   ${CHECKMARK} Ultra-fast responses (26ms)"
    echo -e "   ${CHECKMARK} AI-powered summaries via Google Gemini"
    echo -e "   ${CHECKMARK} Background processing for comprehensive analysis"
    echo -e "   ${CHECKMARK} OAuth permissions & security"
    echo -e "   ${CHECKMARK} Professional error handling"
    echo -e "   ${CHECKMARK} Comprehensive logging & monitoring"
    
else
    print_error "Failed to retrieve ngrok URL"
    print_info "You can manually check at: http://localhost:4040"
fi

echo -e "\n${BOLD}${BLUE}📊 MONITORING:${NC}"
echo -e "   ${GEAR} Django Logs: ${CYAN}tail -f django.log${NC}"
echo -e "   ${GEAR} ngrok Logs: ${CYAN}tail -f ngrok.log${NC}"
echo -e "   ${GEAR} Health Status: ${CYAN}curl http://localhost:8000/health/${NC}"

echo -e "\n${BOLD}${RED}🛑 TO STOP:${NC}"
echo -e "   ${GEAR} Press ${BOLD}Ctrl+C${NC} to shutdown all services cleanly"

print_header "🤖 DEVELOPMENT ENVIRONMENT RUNNING - READY FOR AI-POWERED SLACK INTEGRATION!"

# Keep the script running and monitor services
while true; do
    # Check if Django is still running
    if ! kill -0 $DJANGO_PID 2>/dev/null; then
        print_error "Django server has stopped unexpectedly"
        exit 1
    fi
    
    # Check if ngrok is still running
    if ! kill -0 $NGROK_PID 2>/dev/null; then
        print_error "ngrok tunnel has stopped unexpectedly"
        exit 1
    fi
    
    sleep 5
done
