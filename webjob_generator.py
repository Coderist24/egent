"""
Azure WebJob ZIP Generator Module
Generates ready-to-deploy WebJob packages based on user criteria
"""

import os
import zipfile
import io
import json
from datetime import datetime
from typing import Dict, List, Optional


class WebJobGenerator:
    """Generator for Azure WebJob packages"""
    
    def __init__(self):
        self.template_dir = os.path.dirname(__file__)
    
    def generate_webjob_package(self, config: Dict) -> Optional[bytes]:
        """
        Generate a complete WebJob ZIP package based on configuration
        
        Args:
            config: Configuration dictionary with:
                - agent_id: Agent identifier
                - agent_name: Human-readable agent name
                - data_container: Azure Blob container name for data
                - data_files: List of file names to process
                - schedule_type: 'manual' or 'scheduled'
                - schedule_cron: Cron expression if scheduled (e.g., "0 0 9 * * *")
                - azure_connection_string: Azure Storage connection string
                - openai_api_key: OpenAI API key for processing
        
        Returns:
            Bytes containing the ZIP file, or None if generation fails
        """
        try:
            # Create in-memory ZIP file
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 1. Add run.sh (Linux shell script - entry point for WebJob on Linux)
                run_sh = self._generate_run_sh()
                zip_file.writestr('run.sh', run_sh)
                
                # 2. Add run.cmd (Windows batch script - entry point for WebJob on Windows)
                run_cmd = self._generate_run_cmd()
                zip_file.writestr('run.cmd', run_cmd)
                
                # 3. Add main Python script
                main_script = self._generate_main_script(config)
                zip_file.writestr('run.py', main_script)
                
                # 4. Add requirements.txt
                requirements = self._generate_requirements()
                zip_file.writestr('requirements.txt', requirements)
                
                # 5. Add settings.job (for scheduled jobs)
                if config.get('schedule_type') == 'scheduled':
                    settings_job = self._generate_settings_job(config)
                    zip_file.writestr('settings.job', settings_job)
                
                # 6. Add configuration file
                config_file = self._generate_config_file(config)
                zip_file.writestr('config.json', config_file)
                
                # 7. Add README
                readme = self._generate_readme(config)
                zip_file.writestr('README.md', readme)
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
            
        except Exception as e:
            print(f"Error generating WebJob package: {e}")
            return None
    
    def _generate_run_sh(self) -> str:
        """Generate the run.sh shell script (entry point for WebJob on Linux)"""
        
        script = '''#!/bin/bash
echo "========================================"
echo "Azure WebJob - Data Processing"
echo "========================================"
echo ""

# Install dependencies first
echo "[1/3] Installing Python dependencies..."
python3 -m pip install -r requirements.txt --quiet --disable-pip-version-check
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi
echo "✓ Dependencies installed"

echo ""
echo "[2/3] Running main script..."
python3 run.py
if [ $? -ne 0 ]; then
    echo "ERROR: Script execution failed"
    exit 1
fi

echo ""
echo "[3/3] WebJob completed successfully!"
echo "========================================"
exit 0
'''
        return script
    
    def _generate_run_cmd(self) -> str:
        """Generate the run.cmd batch script (entry point for WebJob)"""
        
        script = '''@echo off
echo ========================================
echo Azure WebJob - Data Processing
echo ========================================
echo.

REM Install dependencies first
echo [1/3] Installing Python dependencies...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)
echo ✓ Dependencies installed

echo.
echo [2/3] Running main script...
python run.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Script execution failed
    exit /b 1
)

echo.
echo [3/3] WebJob completed successfully!
echo ========================================
exit /b 0
'''
        return script
    
    def _generate_main_script(self, config: Dict) -> str:
        """Generate the main Python script for the WebJob"""
        
        agent_id = config.get('agent_id', 'unknown_agent')
        agent_name = config.get('agent_name', 'Unknown Agent')
        data_container = config.get('data_container', '')
        data_files = config.get('data_files', [])
        
        script = f'''#!/usr/bin/env python3
"""
Azure WebJob for {agent_name}
Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

import os
import sys
import json
import logging
import tempfile
import io
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AGENT_ID = "{agent_id}"
AGENT_NAME = "{agent_name}"
DATA_CONTAINER = "{data_container}"
DATA_FILES = {json.dumps(data_files)}

def load_config():
    """Load configuration from config.json or environment"""
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                return json.load(f)
        else:
            return {{}}
    except Exception as e:
        logger.error(f"Error loading config: {{e}}")
        return {{}}

def get_connection_string():
    """Get Azure Storage connection string from environment or config"""
    conn_str = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    if not conn_str:
        config = load_config()
        conn_str = config.get('azure_connection_string')
    return conn_str

def get_ai_project_connection():
    """Get Azure AI Project connection string from config (agent's own config)"""
    config = load_config()
    ai_conn_str = config.get('azure_ai_project_connection_string')
    if not ai_conn_str:
        logger.error("Azure AI Project connection string not found in config.json")
        logger.error("This should be automatically included from agent configuration")
    return ai_conn_str

def get_agent_id():
    """Get Azure AI Agent ID from config (agent's own config)"""
    config = load_config()
    agent_id = config.get('azure_ai_agent_id')
    if not agent_id:
        logger.error("Azure AI Agent ID not found in config.json")
        logger.error("This should be automatically included from agent configuration")
    return agent_id

def upload_file_to_agent(ai_client, agent_id, file_path, filename):
    """Upload a file to Azure AI Agent's Code Interpreter"""
    try:
        # Get file size for logging
        file_size = os.path.getsize(file_path)
        logger.info(f"Uploading {{filename}} ({{file_size:,}} bytes) to AI Agent storage...")
        
        # Read file and create file stream
        with open(file_path, 'rb') as f:
            file_stream = io.BytesIO(f.read())
        file_stream.name = filename
        
        # Upload using upload_file (correct method for AIProjectClient)
        # Purpose is simply "assistants" as a string (no FilePurpose enum needed)
        file_result = ai_client.agents.upload_file(
            file=file_stream,
            purpose="assistants"
        )
        
        if file_result and hasattr(file_result, 'id'):
            file_id = file_result.id
            logger.info(f"✓ File {{filename}} uploaded successfully (ID: {{file_id}})")
            
            # Verify the uploaded file is accessible (with retry logic from reference)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    import time
                    verification_file = ai_client.agents.get_file(file_id=file_id)
                    if verification_file and hasattr(verification_file, 'id'):
                        logger.info(f"✓ File verified: {{verification_file.id}}")
                        return file_id
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(2)
                except Exception as verify_error:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                    else:
                        logger.warning(f"File verification warning: {{verify_error}}")
                        # Return file_id even if verification fails
                        return file_id
            
            return file_id
        else:
            logger.error("Upload failed - no file_id returned")
            return None
            
    except Exception as e:
        error_msg = str(e)
        if "413" in error_msg or "Payload Too Large" in error_msg or "Request Entity Too Large" in error_msg:
            logger.error(f"❌ File too large to upload (413 error): {{filename}}")
            logger.info(f"💡 File size: {{file_size:,}} bytes")
            logger.info(f"💡 The API has a maximum request size limit")
        else:
            logger.error(f"Failed to upload {{filename}} to agent: {{e}}")
        return None

def attach_file_to_agent(ai_client, agent_id, file_id, clear_existing=False):
    """
    Attach uploaded file to the agent's code interpreter tool resources
    
    Args:
        ai_client: Azure AI Project client
        agent_id: The ID of the agent to attach file to
        file_id: The file ID that was uploaded to Azure AI
        clear_existing: If True, clears existing code interpreter files (NOT Knowledge files)
        
    Returns:
        True if file was successfully attached, False otherwise
    """
    try:
        logger.info(f"Attaching file {{file_id}} to agent {{agent_id}} (clear_existing={{clear_existing}})")
        
        # Import Azure AI model classes
        from azure.ai.projects.models import (
            CodeInterpreterToolResource, 
            ToolResources, 
            CodeInterpreterToolDefinition,
            FileSearchToolDefinition,
            FileSearchToolResource
        )
        
        # Get current agent configuration
        current_agent = ai_client.agents.get_agent(agent_id)
        
        # Get existing Code Interpreter file IDs
        current_code_interpreter_files = []
        existing_vector_store_ids = []
        
        if hasattr(current_agent, 'tool_resources') and current_agent.tool_resources:
            # Code Interpreter files
            if hasattr(current_agent.tool_resources, 'code_interpreter') and current_agent.tool_resources.code_interpreter:
                if hasattr(current_agent.tool_resources.code_interpreter, 'file_ids'):
                    current_code_interpreter_files = list(current_agent.tool_resources.code_interpreter.file_ids or [])
                    logger.info(f"Found {{len(current_code_interpreter_files)}} existing code interpreter files")
            
            # Knowledge (File Search) vector stores - PRESERVE THESE
            if hasattr(current_agent.tool_resources, 'file_search') and current_agent.tool_resources.file_search:
                if hasattr(current_agent.tool_resources.file_search, 'vector_store_ids'):
                    existing_vector_store_ids = list(current_agent.tool_resources.file_search.vector_store_ids or [])
                    logger.info(f"Found {{len(existing_vector_store_ids)}} Knowledge vector stores to preserve")
        
        # Prepare new Code Interpreter file list
        if clear_existing:
            # Clear old code interpreter files, add only new file
            new_code_interpreter_files = [file_id]
            logger.info(f"Clearing old code interpreter files, adding new file: {{file_id}}")
        else:
            # Keep existing code interpreter files and add new one
            new_code_interpreter_files = current_code_interpreter_files + [file_id]
            logger.info(f"Keeping {{len(current_code_interpreter_files)}} existing files, adding new file: {{file_id}}")
        
        # Create tool resources (preserve Knowledge vector stores)
        tool_resources = ToolResources(
            code_interpreter=CodeInterpreterToolResource(file_ids=new_code_interpreter_files)
        )
        
        # Add Knowledge vector stores if they exist
        if existing_vector_store_ids:
            tool_resources.file_search = FileSearchToolResource(vector_store_ids=existing_vector_store_ids)
            logger.info(f"Preserved {{len(existing_vector_store_ids)}} Knowledge vector stores")
        
        # Prepare tools list (preserve existing tools)
        tools = []
        if hasattr(current_agent, 'tools') and current_agent.tools:
            tools = list(current_agent.tools)
        
        # Update agent with new tool resources
        updated_agent = ai_client.agents.update_agent(
            agent_id=agent_id,
            name=current_agent.name,  # Preserve agent name
            tools=tools,              # Preserve existing tools
            tool_resources=tool_resources
        )
        
        logger.info(f"✓ File {{file_id}} successfully attached to agent {{updated_agent.id}}")
        
        # Verify attachment with retry logic
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                verification_agent = ai_client.agents.get_agent(agent_id)
                verification_file_ids = []
                if hasattr(verification_agent, 'tool_resources') and verification_agent.tool_resources:
                    if hasattr(verification_agent.tool_resources, 'code_interpreter') and verification_agent.tool_resources.code_interpreter:
                        if hasattr(verification_agent.tool_resources.code_interpreter, 'file_ids'):
                            verification_file_ids = list(verification_agent.tool_resources.code_interpreter.file_ids or [])
                
                if file_id in verification_file_ids:
                    logger.info(f"✓ File {{file_id}} verified in agent")
                    return True
                else:
                    if attempt < max_retries - 1:
                        logger.warning(f"File not yet in agent, retry {{attempt + 1}}/{{max_retries}}")
                        time.sleep(2)
                    else:
                        logger.warning(f"File attachment verification failed after {{max_retries}} attempts")
                        return False
            except Exception as verify_error:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.warning(f"Verification error: {{verify_error}}")
                    return False
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to attach file to agent: {{e}}")
        return False

def process_data_files():
    """Main processing function for data files"""
    logger.info(f"Starting WebJob for {{AGENT_NAME}} ({{AGENT_ID}})")
    logger.info("=" * 60)
    
    try:
        # Get connection strings
        connection_string = get_connection_string()
        if not connection_string:
            logger.error("❌ Azure Storage connection string not found")
            logger.error("Set AZURE_STORAGE_CONNECTION_STRING environment variable")
            sys.exit(1)
        
        ai_connection_string = get_ai_project_connection()
        if not ai_connection_string:
            logger.error("❌ Azure AI Project connection string not found in config.json")
            logger.error("This should be automatically included from agent configuration")
            sys.exit(1)
        
        # Get actual agent ID from config (not the hardcoded one)
        actual_agent_id = get_agent_id()
        if not actual_agent_id:
            logger.error("❌ Azure AI Agent ID not found in config.json")
            logger.error("This should be automatically included from agent configuration")
            sys.exit(1)
        
        logger.info(f"📋 Agent ID from config: {{actual_agent_id}}")
        
        # Create blob service client
        logger.info("📦 Connecting to Azure Blob Storage...")
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(DATA_CONTAINER)
        logger.info(f"✓ Connected to container: {{DATA_CONTAINER}}")
        
        # Create AI Project client
        logger.info("🤖 Connecting to Azure AI Project...")
        credential = DefaultAzureCredential()
        
        # Parse connection string format: endpoint;subscription_id;resource_group;project_name
        try:
            parts = ai_connection_string.split(';')
            if len(parts) >= 4:
                endpoint = parts[0]
                subscription_id = parts[1]
                resource_group = parts[2]
                project_name = parts[3]
            else:
                # Fallback: treat as direct endpoint
                endpoint = ai_connection_string
                subscription_id = None
                resource_group = None
                project_name = None
            
            # Ensure endpoint has https:// prefix
            if not endpoint.startswith('http'):
                endpoint = f"https://{{endpoint}}"
            
            logger.info(f"Endpoint: {{endpoint}}")
            if subscription_id:
                logger.info(f"Subscription: {{subscription_id}}")
                logger.info(f"Resource Group: {{resource_group}}")
                logger.info(f"Project: {{project_name}}")
            
            # Create AI Project client with all parameters
            if subscription_id and resource_group and project_name:
                ai_client = AIProjectClient(
                    credential=credential,
                    endpoint=endpoint,
                    subscription_id=subscription_id,
                    resource_group_name=resource_group,
                    project_name=project_name
                )
            else:
                ai_client = AIProjectClient(
                    credential=credential,
                    endpoint=endpoint
                )
            
            logger.info(f"✓ Connected to AI Project")
        except Exception as conn_error:
            logger.error(f"Failed to parse connection string: {{conn_error}}")
            sys.exit(1)
        
        # Verify agent exists (use actual_agent_id from config)
        try:
            agent = ai_client.agents.get_agent(actual_agent_id)
            logger.info(f"✓ Found agent: {{agent.name}} ({{actual_agent_id}})")
        except Exception as e:
            logger.error(f"❌ Agent {{actual_agent_id}} not found: {{e}}")
            sys.exit(1)
        
        # Process each data file
        logger.info("")
        logger.info(f"📂 Processing {{len(DATA_FILES)}} file(s)...")
        logger.info("=" * 60)
        
        processed_count = 0
        error_count = 0
        uploaded_file_ids = []
        
        for idx, filename in enumerate(DATA_FILES, 1):
            try:
                logger.info(f"[{{idx}}/{{len(DATA_FILES)}}] Processing: {{filename}}")
                
                # Download file from blob
                blob_client = container_client.get_blob_client(filename)
                
                if not blob_client.exists():
                    logger.warning(f"⚠️  File not found in blob storage: {{filename}}")
                    error_count += 1
                    continue
                
                # Download blob data
                blob_data = blob_client.download_blob().readall()
                logger.info(f"  ↓ Downloaded {{len(blob_data):,}} bytes from blob storage")
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                    temp_file.write(blob_data)
                    temp_file_path = temp_file.name
                
                # Upload to AI Agent's Code Interpreter (use actual_agent_id from config)
                file_id = upload_file_to_agent(ai_client, actual_agent_id, temp_file_path, filename)
                
                # Clean up temp file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                
                if file_id:
                    # Attach file to agent (clear code interpreter files only on first upload)
                    clear_existing = (len(uploaded_file_ids) == 0)
                    attach_success = attach_file_to_agent(ai_client, actual_agent_id, file_id, clear_existing)
                    
                    if attach_success:
                        uploaded_file_ids.append({{'filename': filename, 'file_id': file_id}})
                        processed_count += 1
                        logger.info(f"  ✅ Successfully uploaded and attached to Code Interpreter")
                    else:
                        error_count += 1
                        logger.error(f"  ❌ File uploaded but failed to attach to agent")
                else:
                    error_count += 1
                    logger.error(f"  ❌ Failed to upload to Code Interpreter")
                
                logger.info("")
                
            except Exception as file_error:
                logger.error(f"  ❌ Error processing {{filename}}: {{file_error}}")
                error_count += 1
                logger.info("")
        
        # Summary
        logger.info("=" * 60)
        logger.info("📊 EXECUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✓ Files successfully uploaded: {{processed_count}}")
        logger.info(f"✗ Files failed: {{error_count}}")
        logger.info(f"📁 Total files processed: {{len(DATA_FILES)}}")
        
        if uploaded_file_ids:
            logger.info("")
            logger.info("📎 Uploaded Files:")
            for file_info in uploaded_file_ids:
                logger.info(f"  • {{file_info['filename']}} → {{file_info['file_id']}}")
        
        # Write execution log
        execution_log = {{
            'agent_id': AGENT_ID,
            'agent_name': AGENT_NAME,
            'execution_time': datetime.now().isoformat(),
            'processed_count': processed_count,
            'error_count': error_count,
            'total_files': len(DATA_FILES),
            'data_files': DATA_FILES,
            'uploaded_files': uploaded_file_ids
        }}
        
        log_filename = f"logs/webjob_{{AGENT_ID}}_{{datetime.now().strftime('%Y%m%d_%H%M%S')}}.json"
        log_blob_client = container_client.get_blob_client(log_filename)
        log_blob_client.upload_blob(json.dumps(execution_log, indent=2), overwrite=True)
        
        logger.info("")
        logger.info(f"📝 Execution log saved to: {{log_filename}}")
        logger.info("=" * 60)
        
        if error_count == 0:
            logger.info("✅ WebJob completed successfully!")
        else:
            logger.warning(f"⚠️  WebJob completed with {{error_count}} error(s)")
        
        logger.info("=" * 60)
        
        # Exit with appropriate code
        sys.exit(0 if error_count == 0 else 1)
        
    except Exception as e:
        logger.error(f"Fatal error in WebJob: {{e}}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    process_data_files()
'''
        
        return script
    
    def _generate_requirements(self) -> str:
        """Generate requirements.txt for the WebJob"""
        
        requirements = '''# Azure WebJob Requirements
# Core Azure SDKs (same versions as reference v0927-prod-egent2)
azure-storage-blob==12.27.0
azure-identity==1.25.1
azure-ai-projects==1.0.0b10

# Utilities
python-dateutil>=2.8.2
requests>=2.31.0

# Data Processing
pandas>=2.0.0
openpyxl>=3.1.0

# AI Integration
openai>=1.12.0
'''
        
        return requirements
    
    def _generate_settings_job(self, config: Dict) -> str:
        """Generate settings.job for scheduled WebJobs"""
        
        schedule_cron = config.get('schedule_cron', '0 0 9 * * *')  # Default: 9 AM daily
        
        settings = f'''{{
    "schedule": "{schedule_cron}"
}}
'''
        
        return settings
    
    def _generate_config_file(self, config: Dict) -> str:
        """Generate config.json with sanitized configuration"""
        
        safe_config = {
            'agent_id': config.get('agent_id'),
            'agent_name': config.get('agent_name'),
            'azure_ai_project_connection_string': config.get('azure_ai_project_connection_string'),
            'azure_ai_agent_id': config.get('azure_ai_agent_id'),
            'data_container': config.get('data_container'),
            'data_files': config.get('data_files', []),
            'schedule_type': config.get('schedule_type'),
            'generated_at': datetime.now().isoformat()
        }
        
        return json.dumps(safe_config, indent=2)
    
    def _generate_readme(self, config: Dict) -> str:
        """Generate README.md with deployment instructions"""
        
        agent_name = config.get('agent_name', 'Agent')
        schedule_type = config.get('schedule_type', 'manual')
        schedule_cron = config.get('schedule_cron', 'N/A')
        
        readme = f'''# Azure WebJob for {agent_name}

## Overview
This WebJob package was automatically generated for the {agent_name} agent.

**Schedule Type:** {schedule_type}
**Schedule (Cron):** {schedule_cron if schedule_type == 'scheduled' else 'N/A - Run manually'}

## Deployment Instructions

### Prerequisites
1. Azure App Service or Azure WebApp
2. Azure Storage Account with the configured container
3. Python 3.8 or higher runtime

### Deployment Steps

#### Option 1: Azure Portal
1. Navigate to your Azure Web App in the Azure Portal
2. Go to **WebJobs** section
3. Click **Add**
4. Fill in the details:
   - **Name:** {config.get('agent_id', 'webjob')}
   - **File Upload:** Upload this ZIP file
   - **Type:** {"Continuous" if schedule_type == 'scheduled' else "Triggered"}
   - **Scale:** Single Instance
5. Click **OK**

#### Option 2: Azure CLI
```bash
# Login to Azure
az login

# Set variables
RESOURCE_GROUP="your-resource-group"
WEBAPP_NAME="your-webapp-name"
WEBJOB_NAME="{config.get('agent_id', 'webjob')}"

# Deploy WebJob
az webapp webjob triggered upload \\
    --resource-group $RESOURCE_GROUP \\
    --name $WEBAPP_NAME \\
    --webjob-name $WEBJOB_NAME \\
    --file webjob.zip
```

### Environment Variables
**IMPORTANT:** Set this Application Setting in your Web App Configuration:

#### Required Variable:
```bash
# Azure Blob Storage - for reading data files
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
```

**Note:** Azure AI Project connection info is automatically included in the WebJob package from your agent's configuration. No need to set it as environment variable!

#### How to Set Environment Variable:
1. Go to Azure Portal → Your Web App
2. Navigate to **Configuration** → **Application settings**
3. Click **New application setting**
4. Add:
   - **Name:** `AZURE_STORAGE_CONNECTION_STRING`
   - **Value:** Your storage connection string
5. Click **Save** and **Continue**
6. Restart your Web App

#### Finding Your Connection String:
- **Storage Connection String:** Azure Portal → Storage Account → Access Keys → Connection string

### Manual Execution
For manual WebJobs, you can trigger execution via:
- Azure Portal (WebJobs > Select > Run)
- Azure CLI:
  ```bash
  az webapp webjob triggered start \\
      --resource-group $RESOURCE_GROUP \\
      --name $WEBAPP_NAME \\
      --webjob-name $WEBJOB_NAME
  ```

### Monitoring
- View WebJob logs in Azure Portal under WebJobs section
- Check execution logs in the storage container under `logs/` folder
- Monitor Application Insights if configured

### Customization
The main processing logic is in `run.py`. You can modify:
- Data processing logic in the `process_data_files()` function
- File handling and transformation logic
- Error handling and retry mechanisms
- Output format and destination

### Troubleshooting
- Check WebJob logs in Azure Portal
- Verify Azure Storage connection string
- Ensure data files exist in the specified container
- Check Python runtime version compatibility

## Generated Information
- **Generated At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Agent ID:** {config.get('agent_id')}
- **Data Container:** {config.get('data_container')}
- **Data Files:** {', '.join(config.get('data_files', []))}

---
*This WebJob package was automatically generated by the EGEnts AI Platform*
'''
        
        return readme


# Convenience function for direct use
def create_webjob_package(config: Dict) -> Optional[bytes]:
    """
    Create a WebJob package with the given configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        ZIP file bytes or None
    """
    generator = WebJobGenerator()
    return generator.generate_webjob_package(config)
