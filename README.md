# Azure Multi-Agent AI Platform

A comprehensive platform for managing multiple AI agents with document handling and chat capabilities.

## Development Setup

### Prerequisites

1. **Python 3.11+** installed
2. **Azure CLI** installed and authenticated (`az login`)
3. **Azure subscription** with proper permissions

### Quick Start

1. **Clone and navigate to the project directory**
2. **Run the development setup script:**
   ```bash
   python setup_dev_environment.py
   ```
3. **Start the application:**
   ```bash
   streamlit run multi_agent_app.py
   ```

### Manual Setup (Alternative)

1. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   - The application will automatically use `.env.development` for local development
   - Environment variables are already configured in the file

3. **Azure Authentication:**
   - For local development: Uses Service Principal with connection string fallback
   - For production: Uses Managed Identity
   - Make sure you're authenticated with Azure CLI: `az login`

### Environment Configuration

#### Development Mode (Local)
- `DEV_MODE=true` - Enables development mode
- `USE_MANAGED_IDENTITY=false` - Disables managed identity for local dev
- Uses Azure Storage connection string for reliable local access
- Falls back to Azure CLI authentication if needed

#### Production Mode (Azure Web App)
- `DEV_MODE=false` - Enables production mode  
- `USE_MANAGED_IDENTITY=true` - Uses managed identity in Azure
- Uses Azure AD authentication with Service Principal

### Key Features

- **Multi-Agent Support**: Manage multiple AI agents with different specializations
- **Document Processing**: Upload and process PDF, DOCX, and TXT files
- **Azure Integration**: Blob Storage, Search, and AI services
- **User Management**: Role-based access control
- **Modern UI**: Streamlit-based interface with custom styling

### Troubleshooting

#### Authentication Issues
1. **ManagedIdentityCredential errors**: Normal in local development, will fall back to other auth methods
2. **AuthorizationPermissionMismatch**: Check Azure role assignments and storage permissions
3. **Connection timeouts**: Verify network connectivity and Azure service endpoints

#### Common Solutions
- Run `az login` to authenticate with Azure CLI
- Check that storage account and container exist
- Verify Azure role assignments for your user account
- Ensure firewall settings allow access to Azure services

### Azure Resources Required

- **Storage Account**: For configuration and document storage
- **Search Service**: For document indexing and search
- **AI/ML Services**: For agent functionality
- **App Registration**: For authentication (Service Principal)

### File Structure

- `multi_agent_app.py` - Main application entry point
- `azure_utils.py` - Azure service utilities and configuration
- `ui_components.py` - Streamlit UI components
- `.env.development` - Development environment configuration
- `azure-app-settings.env` - Production environment template
- `setup_dev_environment.py` - Development setup script

### Deployment

Use the provided scripts for Azure Web App deployment:
- `azure-config.ps1` (PowerShell)
- `azure-config.sh` (Bash)

Both scripts configure the necessary environment variables in Azure Web App.
