#!/bin/bash
# PaidSearchNav Local Development Startup Script

set -e

echo "🚀 PaidSearchNav Local Development Setup"
echo "========================================"

# Create data directory if it doesn't exist
mkdir -p ./data

# Check if user wants Docker or standalone mode
if [ "$1" = "docker" ]; then
    echo "📦 Starting in Docker mode..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Error: Docker is not running. Please start Docker Desktop."
        exit 1
    fi
    
    # Remove obsolete version warning
    echo "🔧 Building and starting containers..."
    docker-compose up --build
    
elif [ "$1" = "standalone" ] || [ "$1" = "local" ]; then
    echo "🐍 Starting in standalone Python mode..."
    
    # Copy standalone config
    if [ ! -f .env ]; then
        echo "📝 Creating .env from standalone template..."
        cp .env.local.standalone .env
    else
        echo "ℹ️  Using existing .env file"
    fi
    
    # Activate virtual environment
    if [ ! -d ".venv" ]; then
        echo "🔧 Creating virtual environment..."
        python -m venv .venv
    fi
    
    echo "🔌 Activating virtual environment..."
    source .venv/bin/activate
    
    # Install dependencies
    echo "📦 Installing dependencies..."
    uv pip install -e ".[dev,test]"
    
    # Create SQLite database
    echo "🗃️  Setting up SQLite database..."
    alembic upgrade head
    
    # Start application
    echo "🚀 Starting PaidSearchNav API server..."
    echo "📍 Server will be available at: http://localhost:8000"
    echo "📚 API docs will be available at: http://localhost:8000/docs"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""
    uvicorn paidsearchnav.api.main:app --host 0.0.0.0 --port 8000 --reload
    
else
    echo "❓ Usage: $0 [docker|standalone]"
    echo ""
    echo "Modes:"
    echo "  docker     - Run with Docker Compose (PostgreSQL + Redis)"
    echo "  standalone - Run locally with Python (SQLite, no Redis)"
    echo ""
    echo "Examples:"
    echo "  $0 docker      # Full Docker setup"
    echo "  $0 standalone  # Local Python development"
    exit 1
fi