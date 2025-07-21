"""
Startup script for Azure Multi-Agent AI Platform
Run this file to start the application
"""

import subprocess
import sys
import os
import socket
import webbrowser
import time
import threading
import logging
from pathlib import Path

# Set up logging for the startup script
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("startup_debug.log", mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("startup")

def install_requirements():
    """Install required packages"""
    logger.info("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        logger.info("✅ Requirements installed successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error installing requirements: {e}")
        return False
    return True

def find_free_port():
    """Find a free port to use for the application"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def open_browser(url, delay=3):
    """Open browser after a short delay"""
    def delayed_open():
        time.sleep(delay)
        print(f"🌐 Opening browser: {url}")
        webbrowser.open(url)
    
    # Start browser opening in background thread
    thread = threading.Thread(target=delayed_open)
    thread.daemon = True
    thread.start()

def start_application():
    """Start the Streamlit application"""
    logger.info("🚀 Starting Azure Multi-Agent AI Platform...")
    
    # Find a free port
    port = find_free_port()
    logger.info(f"📱 Starting on randomly assigned port {port}...")
    logger.info(f"🌐 Access URL: http://localhost:{port}")
    
    # Debug environment information
    logger.debug("=== ENVIRONMENT DEBUG INFO ===")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Working directory: {os.getcwd()}")
    logger.debug(f"Debug log files: auth_debug.log and startup_debug.log")
    
    # Schedule browser opening - sadece 1 sekme
    url = f"http://localhost:{port}"
    open_browser(url)  # Tek sekme açacak
    
    try:
        # Run the main application with debugging enabled
        cmd = [
            sys.executable, "-m", "streamlit", "run", "multi_agent_app.py",
            "--server.port", str(port),
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false",
            "--server.headless", "true"
        ]
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        # Run the application
        subprocess.run(cmd)
    except KeyboardInterrupt:
        logger.info("\n👋 Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Error starting application on port {port}: {e}", exc_info=True)

def main():
    """Main startup function"""
    # Streamlit'in otomatik tarayıcı açmasını tamamen engelle
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    
    logger.info("🤖 Azure Multi-Agent AI Platform Startup")
    logger.info("=" * 50)
    
    # Log a debug message about debug file locations
    logger.debug("Debug logs will be saved to auth_debug.log and startup_debug.log")
    
    # Check if requirements.txt exists
    if not Path("requirements.txt").exists():
        logger.error("❌ requirements.txt not found!")
        return
    
    # Check if main app exists
    if not Path("multi_agent_app.py").exists():
        logger.error("❌ multi_agent_app.py not found!")
        return
    
    # Install requirements
    if not install_requirements():
        logger.error("❌ Failed to install requirements. Please check your Python environment.")
        return
    
    logger.info("\n" + "=" * 50)
    logger.info("🌟 Setup complete! Starting application...")
    logger.info("📱 Browser will automatically open in a few seconds")
    logger.info("=" * 50)
    
    # Start the application
    start_application()

if __name__ == "__main__":
    main()
