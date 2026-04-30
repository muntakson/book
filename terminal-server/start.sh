#!/bin/bash
# BookMaker Terminal Server Startup Script

set -e

cd "$(dirname "$0")"

echo "🚀 Starting BookMaker Terminal Server..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Creating .env from template..."

    # Copy SECRET_KEY from backend if it exists
    if [ -f "../backend/.env" ]; then
        SECRET_KEY=$(grep SECRET_KEY ../backend/.env | cut -d '=' -f2)
        cat > .env <<EOF
# Terminal Server Configuration
TERMINAL_PORT=8087
SECRET_KEY=${SECRET_KEY}
EOF
        echo "✅ .env created with SECRET_KEY from backend"
    else
        echo "❌ Backend .env not found. Please configure SECRET_KEY manually."
        exit 1
    fi
fi

# Start the server
echo "🐚 Starting terminal server on port 8087..."
node server.js
