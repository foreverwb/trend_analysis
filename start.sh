#!/bin/bash
# ==========================================
# 强势动能交易系统 - Trend Analysis System
# Start Script with Virtual Environment Support
# ==========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR=".venv"
PYTHON_MIN_VERSION="3.10"

echo ""
echo -e "${BLUE}=========================================="
echo " Trend Analysis"
echo -e "==========================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: Please run this script from the trend_analysis directory${NC}"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to compare version numbers
version_ge() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

# Function to get Python version
get_python_version() {
    "$1" -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>/dev/null
}

# ==================== Check Prerequisites ====================
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"

# Find Python
PYTHON_CMD=""
for cmd in python3 python python3.13 python3.12 python3.11 python3.10; do
    if command_exists "$cmd"; then
        version=$(get_python_version "$cmd")
        if [ -n "$version" ] && version_ge "$version" "$PYTHON_MIN_VERSION"; then
            PYTHON_CMD="$cmd"
            echo -e "${GREEN}  ✓ Found Python $version ($cmd)${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python $PYTHON_MIN_VERSION or higher is required but not found.${NC}"
    echo "Please install Python 3.10+ and try again."
    exit 1
fi

# Check Node.js
if ! command_exists node; then
    echo -e "${RED}Error: Node.js is required but not installed.${NC}"
    echo "Please install Node.js and try again."
    exit 1
fi
echo -e "${GREEN}  ✓ Found Node.js $(node --version)${NC}"

# Check npm
if ! command_exists npm; then
    echo -e "${RED}Error: npm is required but not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Found npm $(npm --version)${NC}"

# ==================== Setup Virtual Environment ====================
echo ""
echo -e "${YELLOW}[2/6] Setting up Python virtual environment...${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment in $VENV_DIR..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}  ✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}  ✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}  ✓ Virtual environment activated${NC}"
else
    echo -e "${RED}Error: Could not find virtual environment activation script${NC}"
    exit 1
fi

# ==================== Install Python Dependencies ====================
echo ""
echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"

# Upgrade pip first
pip install --upgrade pip -q

# Install requirements
pip install -r requirements.txt -q
echo -e "${GREEN}  ✓ Python dependencies installed${NC}"

# ==================== Install Node Dependencies ====================
echo ""
echo -e "${YELLOW}[4/6] Installing Node.js dependencies...${NC}"

cd frontend
if [ ! -d "node_modules" ]; then
    npm install
    echo -e "${GREEN}  ✓ Node.js dependencies installed${NC}"
else
    echo -e "${GREEN}  ✓ Node.js dependencies already installed${NC}"
fi
cd ..

# ==================== Create Log Directory ====================
mkdir -p logs
echo -e "${GREEN}  ✓ Log directory ready${NC}"

# ==================== Start Backend ====================
echo ""
echo -e "${YELLOW}[5/6] Starting backend server...${NC}"

# Set PYTHONPATH to project root for proper package imports
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run from project root with proper module path
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "  Waiting for backend to initialize..."
sleep 3

# Check if backend is running
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${GREEN}  ✓ Backend server started (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}Error: Backend server failed to start${NC}"
    exit 1
fi

# ==================== Start Frontend ====================
echo ""
echo -e "${YELLOW}[6/6] Starting frontend server...${NC}"

cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 2

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${GREEN}  ✓ Frontend server started (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}Error: Frontend server failed to start${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# ==================== Display Summary ====================
echo ""
echo -e "${GREEN}=========================================="
echo "  System Started Successfully!"
echo -e "==========================================${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC}  http://localhost:5173"
echo -e "  ${BLUE}Backend:${NC}   http://localhost:8000"
echo -e "  ${BLUE}API Docs:${NC}  http://localhost:8000/docs"
echo ""
echo -e "  ${YELLOW}Configuration:${NC}"
echo "    - Edit config.yaml to change settings"
echo "    - Logs are saved to logs/app.log"
echo ""
echo -e "  ${RED}Press Ctrl+C to stop all services${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Services stopped.${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM

# Wait for processes
wait
