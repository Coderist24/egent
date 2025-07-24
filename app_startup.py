"""
Azure Web App Python startup script for Streamlit
This script handles Azure Web App specific configuration and starts Streamlit
"""

import os
import sys
import subprocess
import logging
import time

# Configure logging for Azure Web App
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("azure_webapp_startup")

def setup_azure_environment():
    """Setup environment variables for Azure Web App"""
    
    # Get port from Azure Web App environment
    port = os.environ.get('PORT', '8000')
    logger.info(f"Azure assigned port: {port}")
    
    # Set Streamlit configuration for Azure Web App
    os.environ['STREAMLIT_SERVER_PORT'] = port
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    os.environ['STREAMLIT_SERVER_ENABLE_CORS'] = 'false'
    os.environ['STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION'] = 'false'
    
    # Azure Web App specific settings
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    # Add current directory to Python path
    current_dir = os.getcwd()
    python_path = os.environ.get('PYTHONPATH', '')
    if current_dir not in python_path:
        if python_path:
            os.environ['PYTHONPATH'] = f"{current_dir}:{python_path}"
        else:
            os.environ['PYTHONPATH'] = current_dir
    
    # Debug environment variables
    logger.info(f"Environment configured:")
    logger.info(f"  - Port: {port}")
    logger.info(f"  - Address: 0.0.0.0")
    logger.info(f"  - Working Directory: {current_dir}")
    logger.info(f"  - Python Path: {os.environ.get('PYTHONPATH')}")
    logger.info(f"  - WEBSITE_SITE_NAME: {os.environ.get('WEBSITE_SITE_NAME', 'Not set')}")
    
    # Check critical Azure environment variables
    azure_vars = {
        'AZURE_CLIENT_ID': os.environ.get('AZURE_CLIENT_ID'),
        'AZURE_TENANT_ID': os.environ.get('AZURE_TENANT_ID'),
        'AZURE_CLIENT_SECRET': os.environ.get('AZURE_CLIENT_SECRET')
    }
    
    for var_name, var_value in azure_vars.items():
        if var_value:
            logger.info(f"  - {var_name}: ***configured***")
        else:
            logger.warning(f"  - {var_name}: NOT SET")
    
    return port

def verify_application_files():
    """Verify that required application files exist"""
    required_files = [
        'multi_agent_app.py',
        'ui_components.py',
        'azure_utils.py',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"Missing required files: {missing_files}")
        return False
    
    logger.info("All required files found")
    return True

def start_streamlit_app(port):
    """Start the Streamlit application with proper configuration"""
    
    try:
        # Build the command with corrected parameters
        cmd = [
            sys.executable, "-m", "streamlit", "run", "multi_agent_app.py",
            "--server.port", str(port),  # Ensure port is string
            "--server.address", "0.0.0.0",
            "--browser.gatherUsageStats", "false",
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false",
            "--logger.level", "debug",  # More verbose logging
            "--server.maxUploadSize", "200"  # Increase upload size limit
        ]
        
        logger.info(f"Starting Streamlit with command: {' '.join(cmd)}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Environment PORT: {os.environ.get('PORT', 'Not set')}")
        
        # Check if main app file exists and is readable
        if not os.path.exists("multi_agent_app.py"):
            logger.error("multi_agent_app.py not found!")
            return False
            
        # Start the process with explicit environment
        env = os.environ.copy()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
        )
        
        # Monitor the process output with timeout
        logger.info("Streamlit process started, monitoring output...")
        startup_timeout = 120  # 2 minutes timeout
        start_time = time.time()
        streamlit_started = False
        
        for line in iter(process.stdout.readline, ''):
            if line:
                print(line.rstrip())  # Print to stdout for Azure logs
                
                # Check for successful startup indicators
                if any(indicator in line for indicator in [
                    "Network URL:", "External URL:", "Local URL:", 
                    "You can now view your Streamlit app", "streamlit run"
                ]):
                    logger.info("✅ Streamlit started successfully!")
                    streamlit_started = True
                
                # Check for errors
                if any(error in line for error in [
                    "ERROR", "Exception", "ModuleNotFoundError", 
                    "ImportError", "SyntaxError", "AttributeError"
                ]):
                    logger.error(f"❌ Streamlit error: {line.rstrip()}")
                
                # Check for port binding success
                if f":{port}" in line and "server" in line.lower():
                    logger.info(f"✅ Server bound to port {port}")
            
            # Timeout check
            if time.time() - start_time > startup_timeout:
                logger.warning("⚠️ Startup timeout reached")
                break
        
        # Wait for process to complete (with timeout)
        try:
            return_code = process.wait(timeout=10)
            logger.info(f"Streamlit process ended with return code: {return_code}")
        except subprocess.TimeoutExpired:
            logger.info("Streamlit process is still running (background mode)")
            return_code = 0
        
        return return_code == 0 or streamlit_started
        
    except Exception as e:
        logger.error(f"Failed to start Streamlit: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Main startup function for Azure Web App"""
    
    logger.info("=" * 60)
    logger.info("🚀 Azure Web App Startup - Multi-Agent AI Platform")
    logger.info("=" * 60)
    
    # Display system information first
    logger.info("📋 System Information:")
    logger.info(f"  - Python version: {sys.version}")
    logger.info(f"  - Working directory: {os.getcwd()}")
    logger.info(f"  - Platform: {sys.platform}")
    
    try:
        logger.info(f"  - Directory contents: {os.listdir('.')}")
    except Exception as e:
        logger.error(f"  - Could not list directory: {e}")
    
    # Setup Azure environment
    logger.info("\n🔧 Setting up Azure environment...")
    port = setup_azure_environment()
    
    # Verify application files
    logger.info("\n📁 Verifying application files...")
    if not verify_application_files():
        logger.error("❌ Application files verification failed!")
        logger.error("This will prevent the application from starting properly.")
        # Don't exit immediately, try to start anyway for debugging
    else:
        logger.info("✅ All required files found")
    
    # Test imports
    logger.info("\n🐍 Testing Python imports...")
    try:
        import streamlit
        logger.info(f"✅ Streamlit version: {streamlit.__version__}")
    except ImportError as e:
        logger.error(f"❌ Streamlit import failed: {e}")
        
    try:
        # Test if main app can be imported
        sys.path.insert(0, os.getcwd())
        import multi_agent_app
        logger.info("✅ Main application import successful")
    except Exception as e:
        logger.error(f"❌ Main application import failed: {e}")
        logger.error("This may indicate missing dependencies or syntax errors")
    
    # Start Streamlit
    logger.info(f"\n🚀 Starting Streamlit application on port {port}...")
    logger.info(f"🌐 Expected URL: http://0.0.0.0:{port}")
    
    success = start_streamlit_app(port)
    
    if not success:
        logger.error("❌ Failed to start Streamlit application")
        logger.error("Check the logs above for specific error messages")
        sys.exit(1)
    else:
        logger.info("✅ Streamlit application started successfully")

if __name__ == "__main__":
    main()
