#!/bin/bash

# Script de démarrage Trade Cursor v7.0 avec frontend Svelte

echo "🚀 Starting Trade Cursor v7.0 with Svelte Frontend"
echo "=================================================="

# Check if in correct directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from trade_cursor_py directory"
    exit 1
fi

# Check if frontend exists
if [ ! -d "frontend" ]; then
    echo "❌ Error: frontend directory not found"
    exit 1
fi

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    echo "Please install Node.js 18+ from https://nodejs.org"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Error: Node.js version must be 18 or higher"
    echo "Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js version: $(node -v)"

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo ""
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Error: npm install failed"
        exit 1
    fi
    cd ..
    echo "✅ Dependencies installed"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

echo "✅ Python version: $(python3 --version)"

# Start backend
echo ""
echo "🐍 Starting FastAPI backend (port 5000)..."
python3 main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend is running
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "❌ Error: Backend failed to start"
    exit 1
fi

echo "✅ Backend started (PID: $BACKEND_PID)"

# Start frontend
echo ""
echo "⚡ Starting Svelte frontend (port 3000)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 2

# Check if frontend is running
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo "❌ Error: Frontend failed to start"
    kill $BACKEND_PID
    exit 1
fi

echo "✅ Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "=================================================="
echo "🎉 Trade Cursor v7.0 is running!"
echo ""
echo "📍 Frontend:  http://localhost:3000"
echo "📍 Backend:   http://localhost:5000"
echo "📍 API:       http://localhost:5000/api/state"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "=================================================="

# Trap Ctrl+C to stop both processes
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID; echo '✅ Stopped'; exit 0" INT

# Keep script running
wait
