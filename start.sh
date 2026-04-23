#!/bin/bash
# ✈ Agentic AI Workflow for Aeroplanes - Quick Start Script
# Run this from the project root: bash start.sh

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "  ✈  AGENTIC AI WORKFLOW FOR AEROPLANES"
echo "  ══════════════════════════════════════"
echo -e "${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $(python3 --version | cut -d' ' -f2) found${NC}"

# Check Node
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js 18+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node $(node --version) found${NC}"

# Setup backend
echo -e "\n${YELLOW}▸ Setting up backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "  Installing Python packages..."
pip install -r requirements.txt -q

echo "  Installing Playwright browsers..."
playwright install chromium --quiet 2>/dev/null || playwright install chromium

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}  ⚠ Created .env from template. Add your ANTHROPIC_API_KEY for Vision Agent.${NC}"
fi

cd ..

# Setup frontend
echo -e "\n${YELLOW}▸ Setting up frontend...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    echo "  Installing npm packages..."
    npm install --silent
fi

cd ..

echo -e "\n${GREEN}✓ Setup complete!${NC}"
echo ""
echo -e "${BLUE}Starting servers...${NC}"
echo ""

# Start backend in background
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

sleep 2

# Start frontend
echo -e "${GREEN}✓ Backend running (PID: $BACKEND_PID)${NC}"
echo -e "${GREEN}✓ Starting frontend at http://localhost:5173${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop both servers"
echo ""

cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Trap Ctrl+C to kill both
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

wait $FRONTEND_PID
