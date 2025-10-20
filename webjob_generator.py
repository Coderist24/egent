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
                # 1. Add main Python script
                main_script = self._generate_main_script(config)
                zip_file.writestr('run.py', main_script)
                
                # 2. Add requirements.txt
                requirements = self._generate_requirements()
                zip_file.writestr('requirements.txt', requirements)
                
                # 3. Add settings.job (for scheduled jobs)
                if config.get('schedule_type') == 'scheduled':
                    settings_job = self._generate_settings_job(config)
                    zip_file.writestr('settings.job', settings_job)
                
                # 4. Add configuration file
                config_file = self._generate_config_file(config)
                zip_file.writestr('config.json', config_file)
                
                # 5. Add README
                readme = self._generate_readme(config)
                zip_file.writestr('README.md', readme)
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
            
        except Exception as e:
            print(f"Error generating WebJob package: {e}")
            return None
    
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
from datetime import datetime
from azure.storage.blob import BlobServiceClient

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

def process_data_files():
    """Main processing function for data files"""
    logger.info(f"Starting WebJob for {{AGENT_NAME}} ({{AGENT_ID}})")
    
    try:
        # Get connection string
        connection_string = get_connection_string()
        if not connection_string:
            logger.error("Azure Storage connection string not found")
            sys.exit(1)
        
        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(DATA_CONTAINER)
        
        # Process each data file
        processed_count = 0
        error_count = 0
        
        for filename in DATA_FILES:
            try:
                logger.info(f"Processing file: {{filename}}")
                
                # Download file
                blob_client = container_client.get_blob_client(filename)
                
                if not blob_client.exists():
                    logger.warning(f"File not found: {{filename}}")
                    error_count += 1
                    continue
                
                # Download blob data
                blob_data = blob_client.download_blob().readall()
                logger.info(f"Downloaded {{len(blob_data)}} bytes from {{filename}}")
                
                # Here you can add your custom processing logic
                # For example: parse Excel, process CSV, analyze data, etc.
                
                # Example: Save to processed folder
                processed_filename = f"processed/{{filename}}"
                processed_blob_client = container_client.get_blob_client(processed_filename)
                processed_blob_client.upload_blob(blob_data, overwrite=True)
                
                processed_count += 1
                logger.info(f"Successfully processed: {{filename}}")
                
            except Exception as file_error:
                logger.error(f"Error processing {{filename}}: {{file_error}}")
                error_count += 1
        
        # Summary
        logger.info(f"WebJob completed: {{processed_count}} files processed, {{error_count}} errors")
        
        # Write execution log
        execution_log = {{
            'agent_id': AGENT_ID,
            'agent_name': AGENT_NAME,
            'execution_time': datetime.now().isoformat(),
            'processed_count': processed_count,
            'error_count': error_count,
            'data_files': DATA_FILES
        }}
        
        log_filename = f"logs/execution_{{datetime.now().strftime('%Y%m%d_%H%M%S')}}.json"
        log_blob_client = container_client.get_blob_client(log_filename)
        log_blob_client.upload_blob(json.dumps(execution_log, indent=2), overwrite=True)
        
        logger.info(f"Execution log saved to: {{log_filename}}")
        
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
azure-storage-blob>=12.19.0
azure-identity>=1.15.0
python-dateutil>=2.8.2
requests>=2.31.0

# Optional: For data processing
pandas>=2.0.0
openpyxl>=3.1.0

# Optional: For OpenAI integration
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
Set these Application Settings in your Web App:

```
AZURE_STORAGE_CONNECTION_STRING=<your-storage-connection-string>
```

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
