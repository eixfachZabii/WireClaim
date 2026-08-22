#!/usr/bin/env bash
# ==============================================================================
# WireClaim - Setup & Run Script
# Automates venv creation, dependency installation, and main.py execution.
# ==============================================================================

set -e

# Change directory to script's parent folder
cd "$(dirname "$0")"

echo "================================================================="
echo "  🚀 WireClaim - QuantCo Tournament Runner"
echo "================================================================="

# 1. Locate Python executable
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
elif command -v py &>/dev/null; then
    PYTHON_BIN="py"
else
    echo "❌ Error: Python is not installed or not found in PATH."
    exit 1
fi

echo "✓ Using Python: $($PYTHON_BIN --version 2>&1)"

# 2. Check and initialize .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "ℹ️  Creating '.env' from '.env.example'..."
        cp .env.example .env
        echo "⚠️  Please configure your 'TEAM_API_KEY' in the newly created '.env' file."
    fi
fi

# 3. Create virtual environment (.venv) if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    $PYTHON_BIN -m venv .venv
    echo "✓ Virtual environment created."
fi

# 4. Activate virtual environment (cross-platform support for Unix and Windows/Git-Bash)
if [ -f ".venv/Scripts/activate" ]; then
    # Windows (Git Bash, MSYS, Cygwin)
    # shellcheck disable=SC1091
    source ".venv/Scripts/activate"
elif [ -f ".venv/bin/activate" ]; then
    # Linux, macOS, WSL
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
else
    echo "❌ Error: Virtual environment activation script not found in .venv."
    exit 1
fi

echo "✓ Activated virtual environment (.venv)"

# 5. Install / upgrade dependencies from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "📥 Installing dependencies from requirements.txt..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo "✓ Dependencies are up to date."
fi

# 6. Run WireClaim main script with any arguments passed to run.sh
echo "▶ Running main.py..."
python main.py "$@"
