#!/bin/bash
# Django Slack Bot - ngrok Setup Script
# This script automatically installs and configures ngrok for your Django Slack bot

set -e  # Exit on any error

echo "🚀 Django Slack Bot - ngrok Setup"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "mac";;
        Linux*)     echo "linux";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

# Get ngrok download URL based on OS and architecture
get_ngrok_url() {
    local os=$1
    local arch=$(uname -m)
    
    case $arch in
        x86_64|amd64) arch="amd64";;
        arm64|aarch64) arch="arm64";;
        i386|i686) arch="386";;
        *) arch="amd64";; # Default to amd64
    esac
    
    case $os in
        mac)
            echo "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-${arch}.zip"
            ;;
        linux)
            echo "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-${arch}.tgz"
            ;;
        windows)
            echo "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-${arch}.zip"
            ;;
        *)
            print_error "Unsupported operating system: $os"
            exit 1
            ;;
    esac
}

# Check if ngrok is installed
check_ngrok() {
    if command -v ngrok &> /dev/null; then
        print_success "ngrok is already installed globally"
        return 0
    elif [ -f "./ngrok" ]; then
        print_success "ngrok found in current directory"
        return 0
    else
        return 1
    fi
}

# Download and install ngrok
install_ngrok() {
    local os=$(detect_os)
    print_info "Detected OS: $os"
    
    if [ "$os" = "unknown" ]; then
        print_error "Unable to detect your operating system"
        exit 1
    fi
    
    local url=$(get_ngrok_url $os)
    local filename="ngrok-download"
    
    print_info "Downloading ngrok from: $url"
    
    # Download ngrok
    if command -v curl &> /dev/null; then
        curl -L -o "$filename" "$url"
    elif command -v wget &> /dev/null; then
        wget -O "$filename" "$url"
    else
        print_error "Neither curl nor wget is available. Please install one of them."
        exit 1
    fi
    
    # Extract based on file type
    print_info "Extracting ngrok..."
    case $url in
        *.zip)
            if command -v unzip &> /dev/null; then
                unzip -o "$filename" ngrok
            else
                print_error "unzip command not found. Please install unzip."
                exit 1
            fi
            ;;
        *.tgz|*.tar.gz)
            if command -v tar &> /dev/null; then
                tar -xzf "$filename" ngrok
            else
                print_error "tar command not found. Please install tar."
                exit 1
            fi
            ;;
    esac
    
    # Make executable
    chmod +x ngrok
    
    # Clean up
    rm "$filename"
    
    print_success "ngrok installed successfully in current directory"
}

# Get ngrok executable path
get_ngrok_path() {
    if command -v ngrok &> /dev/null; then
        echo "ngrok"
    elif [ -f "./ngrok" ]; then
        echo "./ngrok"
    else
        echo ""
    fi
}

# Configure ngrok auth token
configure_ngrok() {
    local ngrok_path=$(get_ngrok_path)
    
    if [ -z "$ngrok_path" ]; then
        print_error "ngrok not found"
        exit 1
    fi
    
    # Check if already configured
    if $ngrok_path config check &> /dev/null; then
        print_success "ngrok is already configured with an auth token"
        return 0
    fi
    
    print_info "ngrok needs to be configured with your auth token"
    echo ""
    echo "To get your auth token:"
    echo "1. Go to https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "2. Sign up/login to ngrok"
    echo "3. Copy your auth token"
    echo ""
    
    read -p "Enter your ngrok auth token: " auth_token
    
    if [ -z "$auth_token" ]; then
        print_error "Auth token cannot be empty"
        exit 1
    fi
    
    print_info "Configuring ngrok with auth token..."
    $ngrok_path config add-authtoken "$auth_token"
    
    print_success "ngrok configured successfully"
}

# Create start_dev.sh script
create_start_dev_script() {
    local ngrok_path=$(get_ngrok_path)
    
    cat > start_dev.sh << 'EOF'
#!/bin/bash
# Django Slack Bot - Development Server with ngrok
# This script runs both Django and ngrok together

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_highlight() { echo -e "${CYAN}🔗 $1${NC}"; }

# Function to cleanup processes on exit
cleanup() {
    print_info "Shutting down servers..."
    if [ ! -z "$DJANGO_PID" ]; then
        kill $DJANGO_PID 2>/dev/null || true
        print_info "Django server stopped"
    fi
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
        print_info "ngrok stopped"
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Determine ngrok path
NGROK_PATH="ngrok"
if [ -f "./ngrok" ]; then
    NGROK_PATH="./ngrok"
fi

print_info "Starting Django Slack Bot Development Environment"
echo "=================================================="
echo ""

# Start Django server in background
print_info "Starting Django server..."
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 manage.py runserver 127.0.0.1:8000 > django.log 2>&1 &
DJANGO_PID=$!

# Wait for Django to start
print_info "Waiting for Django to start..."
sleep 3

# Check if Django is running
if ! ps -p $DJANGO_PID > /dev/null; then
    print_error "Failed to start Django server. Check django.log for details."
    exit 1
fi

print_success "Django server started (PID: $DJANGO_PID)"

# Start ngrok
print_info "Starting ngrok tunnel..."
$NGROK_PATH http 8000 --log stdout > ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 3

# Get ngrok public URL
print_info "Getting ngrok public URL..."
for i in {1..10}; do
    if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
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
")
        if [ ! -z "$NGROK_URL" ]; then
            break
        fi
    fi
    sleep 2
done

echo ""
echo "🎉 Development Environment Ready!"
echo "================================="
echo ""
print_success "Django server: http://127.0.0.1:8000/"
if [ ! -z "$NGROK_URL" ]; then
    print_highlight "Public URL: $NGROK_URL"
    print_highlight "Slack webhook: $NGROK_URL/slack/events/"
    echo ""
    print_info "ngrok Web Interface: http://localhost:4040"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Copy the webhook URL above"
    echo "2. Go to your Slack app settings"
    echo "3. Update the Event Subscriptions URL with: $NGROK_URL/slack/events/"
    echo "4. Save the settings in Slack"
else
    print_warning "Could not retrieve ngrok URL. Check ngrok.log for details."
fi
echo ""
print_info "Press Ctrl+C to stop both servers"
echo ""

# Keep script running and show logs
tail -f django.log &
wait $DJANGO_PID
EOF

    # Replace the Python path placeholder with the actual path
    chmod +x start_dev.sh
    print_success "start_dev.sh created successfully"
}

# Create ngrok config file template
create_ngrok_config() {
    cat > .ngrok.yml << 'EOF'
# ngrok Configuration File for Django Slack Bot
# ==============================================
# 
# This file configures ngrok tunneling for your Django Slack bot.
# Place this file in your project root directory.

version: "2"

# Web interface configuration
web_addr: localhost:4040

# Tunnel configurations
tunnels:
  django-bot:
    proto: http
    addr: 8000
    # Uncomment and set a custom subdomain (requires paid plan)
    # subdomain: my-slack-bot
    
    # Add custom headers
    request_headers:
      # Skip ngrok browser warning
      ngrok-skip-browser-warning: "true"
    
    # Basic auth (optional)
    # auth: "username:password"
    
    # IP restrictions (optional)
    # allow_cidrs:
    #   - "0.0.0.0/0"

# Global settings
log_level: info
log_format: term

# Update check (set to false to disable)
update_check: true

# Metadata (optional, for organization)
metadata: '{"service": "django-slack-bot", "env": "development"}'

# Uncomment to use a custom config location
# config_path: /path/to/ngrok.yml

# ========================================
# Configuration Options Explained:
# ========================================
#
# subdomain: Creates a consistent URL (requires paid plan)
#   Example: https://my-bot.ngrok.io instead of random URLs
#
# auth: Adds basic authentication to your tunnel
#   Format: "username:password"
#
# allow_cidrs: Restricts access to specific IP ranges
#   Use "0.0.0.0/0" to allow all IPs
#
# request_headers: Add custom headers to all requests
#   "ngrok-skip-browser-warning": Skips the ngrok browser warning
#
# To get a permanent subdomain:
# 1. Upgrade to ngrok paid plan at https://dashboard.ngrok.com/billing
# 2. Uncomment the subdomain line above
# 3. Replace "my-slack-bot" with your desired subdomain
#
# For more options, visit: https://ngrok.com/docs/ngrok-agent/config
EOF

    print_success ".ngrok.yml config template created"
}

# Main setup function
main() {
    echo ""
    
    # Check if ngrok is installed
    if ! check_ngrok; then
        print_info "ngrok not found. Installing..."
        install_ngrok
    fi
    
    # Configure ngrok
    print_info "Configuring ngrok..."
    configure_ngrok
    
    # Create development script
    print_info "Creating development scripts..."
    create_start_dev_script
    create_ngrok_config
    
    echo ""
    print_success "🎉 ngrok setup completed successfully!"
    echo ""
    echo "📋 What was created:"
    echo "  • ngrok binary (if not already installed)"
    echo "  • start_dev.sh - Runs Django + ngrok together"
    echo "  • .ngrok.yml - ngrok configuration template"
    echo ""
    echo "🚀 Quick Start:"
    echo "  ./start_dev.sh    # Start development environment"
    echo ""
    echo "🔧 Manual Commands:"
    echo "  ./run.sh          # Start only Django"
    echo "  ./ngrok http 8000 # Start only ngrok (after Django)"
    echo ""
    print_warning "Remember to update your Slack app's webhook URL with the ngrok URL!"
    echo ""
}

# Run main function
main "$@" 