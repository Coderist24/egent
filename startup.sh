#!/bin/bash

# Azure Web App startup script for Streamlit application

# Set environment variables for Streamlit
export STREAMLIT_SERVER_PORT=${PORT:-8000}
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_SERVER_ENABLE_CORS=false
export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

# Azure Web App specific environment
export PYTHONUNBUFFERED=1
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

# Create necessary directories
mkdir -p /tmp/streamlit
chmod 777 /tmp/streamlit

# Verify main application file exists
if [ ! -f "multi_agent_app.py" ]; then
    echo "ERROR: multi_agent_app.py not found!"
    exit 1
fi

# Install dependencies if requirements.txt exists (though Azure should handle this)
if [ -f requirements.txt ]; then
    pip list | grep streamlit || pip install -r requirements.txt
fi

# Start the Streamlit application
exec python -m streamlit run multi_agent_app.py \
    --server.port=$STREAMLIT_SERVER_PORT \
    --server.address=$STREAMLIT_SERVER_ADDRESS \
    --browser.gatherUsageStats=$STREAMLIT_BROWSER_GATHER_USAGE_STATS \
    --server.headless=$STREAMLIT_SERVER_HEADLESS \
    --server.enableCORS=$STREAMLIT_SERVER_ENABLE_CORS \
    --server.enableXsrfProtection=$STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION \
    --logger.level=debug
