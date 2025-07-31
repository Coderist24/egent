"""
Azure Multi-Agent AI Document Management and Chat System
A comprehensive platform for managing multiple AI agents with document handling and chat capabilities
"""

import streamlit as st
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    import os
    
    # Load from azure-app-settings.env file
    env_path = os.path.join(os.path.dirname(__file__), 'azure-app-settings.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Import Azure utilities with fallback
try:
    from azure_utils import AzureConfig, EnhancedAzureAIAgentClient, AzureAuthenticator, BlobStorageUserManager, BlobStorageAgentManager
    AZURE_AVAILABLE = True
    logger.info("Azure utilities loaded successfully")
except ImportError as e:
    # Fallback classes for when Azure utilities are not available
    AZURE_AVAILABLE = False
    logger.warning(f"Azure utilities not available: {e}. Using fallback mode.")
    
    class AzureConfig:
        def __init__(self):
            pass
    
    class BlobStorageAgentManager:
        def __init__(self, config):
            pass
        def get_active_agents(self):
            return {}
        def get_agent(self, agent_id):
            return None
        def get_all_agents(self):
            return {}
        def add_agent(self, config):
            return False
        def update_agent(self, agent_id, config):
            return False
        def delete_agent(self, agent_id):
            return False
        def set_agent_status(self, agent_id, status):
            return False
        def generate_azure_container_name(self, agent_id):
            return f"{agent_id}-documents"
    
    class BlobStorageUserManager:
        def __init__(self, config):
            pass
        def authenticate_admin(self, username, password):
            # Simple fallback authentication
            return username == "admin" and password == "admin"
        def authenticate_azure_user(self, username, password):
            return {"success": False, "error": "Azure authentication not available"}
        def get_user_permissions(self, username):
            return {"role": "admin", "permissions": ["all"]} if username == "admin" else {}
        def get_user(self, username):
            return {"username": username, "role": "admin"} if username == "admin" else None
        def has_permission(self, username, agent_id, permission_type):
            return username == "admin"
        def add_user(self, username, role, password, permissions=None):
            return False
        def update_user_permissions(self, username, permissions):
            return False
        def delete_user(self, username):
            return False
        def get_all_users(self):
            return {"admin": {"username": "admin", "role": "admin", "permissions": ["all"]}}
    
    class EnhancedAzureAIAgentClient:
        def __init__(self, *args, **kwargs):
            pass
    
    class AzureAuthenticator:
        def __init__(self, *args, **kwargs):
            pass

# Document processing imports (lazy loaded)
import io

# Page configuration
st.set_page_config(
    page_title="EGEnts AI Platform",
    page_icon="�",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        background: linear-gradient(90deg, #0078d4, #106ebe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    
    .logo-header {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .company-logo {
        height: 80px;
        width: auto;
        margin-right: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .company-title {
        font-size: 2.5rem;
        background: linear-gradient(90deg, #0078d4, #106ebe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
        margin: 0;
    }
    
    .company-subtitle {
        font-size: 1.2rem;
        color: #666;
        margin: 0;
        font-weight: 300;
    }
    
    .agent-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid #e0e0e0;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .agent-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border-color: #0078d4;
    }
    
    .agent-icon {
        font-size: 3rem;
        text-align: center;
    }
    
    .agent-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .agent-description {
        color: #666;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .agent-stats {
        background: rgba(255,255,255,0.8);
        border-radius: 10px;
        padding: 0.5rem;
        font-size: 0.8rem;
        color: #555;
    }
    /* .login-container ve büyük login butonu kaldırıldı */
    
    /* WhatsApp benzeri chat baloncukları */
    .chat-container {
        background: transparent;
        padding: 0;
        border-radius: 0;
        min-height: 0;
        overflow-y: auto;
        margin: 0;
    }
    
    .message-bubble {
        max-width: 70%;
        margin: 0.5rem 0;
        padding: 0.8rem 1.2rem;
        border-radius: 18px;
        word-wrap: break-word;
        position: relative;
        animation: fadeIn 0.3s ease-in;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .user-message {
        background: #dcf8c6;
        margin-left: 1rem;
        margin-right: auto;
        border-bottom-left-radius: 5px;
        border: 1px solid #b7e4a3;
    }
    
    .user-message::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: -8px;
        width: 0;
        height: 0;
        border: 8px solid transparent;
        border-right-color: #dcf8c6;
        border-bottom: 0;
    }
    
    .assistant-message {
        background: #ffffff;
        margin-left: auto;
        margin-right: 1rem;
        border-bottom-right-radius: 5px;
        border: 1px solid #e5e5ea;
    }
    
    .assistant-message::after {
        content: '';
        position: absolute;
        bottom: 0;
        right: -8px;
        width: 0;
        height: 0;
        border: 8px solid transparent;
        border-left-color: #ffffff;
        border-bottom: 0;
    }
    
    .message-time {
        font-size: 0.7rem;
        color: #666;
        margin-top: 0.3rem;
        text-align: right;
    }
    
    .message-sender {
        font-size: 0.8rem;
        font-weight: bold;
        margin-bottom: 0.3rem;
        color: #0078d4;
    }
    
    .document-reference {
        color: #0078d4 !important;
        font-weight: 900 !important;
        font-style: normal !important;
        background-color: rgba(0, 120, 212, 0.2) !important;
        padding: 8px 14px !important;
        border-radius: 8px !important;
        border: 2px solid #0078d4 !important;
        display: inline-block !important;
        margin: 3px 5px !important;
        transition: all 0.3s ease !important;
        text-decoration: none !important;
        font-size: 1.0em !important;
        box-shadow: 0 2px 4px rgba(0, 120, 212, 0.3) !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
    }
    
    /* Daha güçlü CSS kuralları için tüm olası etiketleri hedefle */
    span.document-reference,
    div.document-reference,
    .document-reference span,
    .document-reference * {
        color: #0078d4 !important;
        font-weight: 900 !important;
        font-size: 1.0em !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
    }
    
    /* Streamlit'in varsayılan stillerini override et */
    .stMarkdown .document-reference,
    .stMarkdown span.document-reference,
    [data-testid="stMarkdownContainer"] .document-reference,
    [data-testid="stChatMessage"] .document-reference {
        color: #0078d4 !important;
        font-weight: 900 !important;
        background-color: rgba(0, 120, 212, 0.2) !important;
        padding: 8px 14px !important;
        border-radius: 8px !important;
        border: 2px solid #0078d4 !important;
        display: inline-block !important;
        margin: 3px 5px !important;
        text-decoration: none !important;
        font-size: 1.0em !important;
        box-shadow: 0 2px 4px rgba(0, 120, 212, 0.3) !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
    }
    
    /* En güçlü CSS kuralı - her şeyi override et */
    *[class*="document-reference"] {
        color: #0078d4 !important;
        font-weight: 900 !important;
        background-color: rgba(0, 120, 212, 0.2) !important;
        padding: 8px 14px !important;
        border-radius: 8px !important;
        border: 2px solid #0078d4 !important;
        display: inline-block !important;
        margin: 3px 5px !important;
        text-decoration: none !important;
        font-size: 1.0em !important;
        box-shadow: 0 2px 4px rgba(0, 120, 212, 0.3) !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
    }
    
    .document-reference:hover {
        background-color: rgba(0, 120, 212, 0.35) !important;
        border-color: #005a9e !important;
        transform: scale(1.05) !important;
        box-shadow: 0 4px 8px rgba(0, 120, 212, 0.5) !important;
        cursor: pointer !important;
        color: #005a9e !important;
    }
    
    /* Chat mesajları için özel kurallar */
    .assistant-message .document-reference,
    .user-message .document-reference,
    .message-bubble .document-reference {
        color: #0078d4 !important;
        font-weight: 900 !important;
        background-color: rgba(0, 120, 212, 0.2) !important;
        padding: 8px 14px !important;
        border-radius: 8px !important;
        border: 2px solid #0078d4 !important;
        display: inline-block !important;
        margin: 3px 5px !important;
        text-decoration: none !important;
        font-size: 1.0em !important;
        box-shadow: 0 2px 4px rgba(0, 120, 212, 0.3) !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
    }
    
    /* Streamlit'in varsayılan stillerini override et */
    .stMarkdown .document-reference,
    .stMarkdown span.document-reference,
    [data-testid="stMarkdownContainer"] .document-reference,
    [data-testid="stChatMessage"] .document-reference {
        color: #0078d4 !important;
        font-weight: 900 !important;
        background-color: rgba(0, 120, 212, 0.2) !important;
        padding: 8px 14px !important;
        border-radius: 8px !important;
        border: 2px solid #0078d4 !important;
        display: inline-block !important;
        margin: 3px 5px !important;
        text-decoration: none !important;
        font-size: 1.0em !important;
        box-shadow: 0 2px 4px rgba(0, 120, 212, 0.3) !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
    }
    
    .error-message {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        border-left: 4px solid #f44336;
        color: #c62828;
    }
    
    .success-message {
        background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
        border-left: 4px solid #4caf50;
        color: #2e7d32;
    }
    
    .login-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        color: white;
    }
    
    .nav-tab {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border: none;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        margin: 0.2rem;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .nav-tab:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    .nav-tab.active {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        transform: scale(1.05);
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .permissions-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .permission-card {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #ddd;
    }
    
    .document-card {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #ddd;
    }
    
    .icon-selector-button {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border: 2px solid #dee2e6;
        border-radius: 10px;
        padding: 0.8rem;
        margin: 0.2rem;
        font-size: 1.5rem;
        cursor: pointer;
        transition: all 0.3s ease;
        text-align: center;
        min-height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .icon-selector-button:hover {
        background: linear-gradient(135deg, #0078d4 0%, #106ebe 100%);
        border-color: #0078d4;
        transform: scale(1.05);
        box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
        color: white;
    }
    
    .icon-selected {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        border-color: #28a745;
        color: white;
        transform: scale(1.05);
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
    }
    
    .icon-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
        gap: 0.5rem;
        margin: 1rem 0;
        padding: 1rem;
        background: #f8f9fa;
        border-radius: 10px;
        border: 1px solid #dee2e6;
    }
    
    .code-interpreter-image {
        max-width: 100%;
        height: auto;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
    }
    
    .code-snippet-container {
        background: #f8f9fa;
        border-radius: 10px;
        margin: 0.5rem 0;
        border: 1px solid #dee2e6;
    }
    
    .code-snippet-header {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px 10px 0 0;
        font-weight: bold;
        font-size: 0.9rem;
    }
    
    .download-section {
        background: #f8f9fa;
        border-radius: 15px;
        padding: 1rem;
        margin: 1rem 0;
        border: 2px solid #e9ecef;
    }
    
    .download-file-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #2196f3;
        text-align: center;
    }
    
    .download-btn {
        background: linear-gradient(135deg, #0078d4 0%, #106ebe 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
        text-decoration: none;
        display: inline-block;
        margin: 5px;
    }
    
    .download-btn:hover {
        background: linear-gradient(135deg, #106ebe 0%, #005a9e 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
    }
    
    .stDownloadButton > button {
        background: linear-gradient(135deg, #0078d4 0%, #106ebe 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #106ebe 0%, #005a9e 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Configuration class for Azure services
# Lazy loading for heavy libraries
@st.cache_resource
def load_heavy_libraries():
    """Load heavy libraries only when needed for performance optimization"""
    try:
        import PyPDF2
        import docx
        return {
            'PyPDF2': PyPDF2,
            'docx': docx
        }
    except ImportError as e:
        return {}

# Agent configuration and management
class AgentManager:
    """Manages agent configurations and operations - now using blob storage"""
    
    def __init__(self, config: AzureConfig):
        # Initialize without any extra parameters
        self.blob_agent_manager = BlobStorageAgentManager(config)
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent configuration by ID"""
        try:
            return self.blob_agent_manager.get_agent(agent_id)
        except TypeError as e:
            # Handle the error gracefully
            return None
    
    def get_all_agents(self) -> Dict[str, Dict]:
        """Get all agent configurations"""
        return self.blob_agent_manager.get_all_agents()
    
    def get_active_agents(self) -> Dict[str, Dict]:
        """Get only active agent configurations"""
        return self.blob_agent_manager.get_active_agents()
    
    def add_agent(self, agent_config: Dict) -> bool:
        """Add a new agent configuration"""
        return self.blob_agent_manager.add_agent(agent_config)
    
    def update_agent(self, agent_id: str, agent_config: Dict) -> bool:
        """Update an existing agent configuration"""
        return self.blob_agent_manager.update_agent(agent_id, agent_config)
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent configuration"""
        return self.blob_agent_manager.delete_agent(agent_id)
    
    def set_agent_status(self, agent_id: str, status: str) -> bool:
        """Set agent status (active/inactive)"""
        return self.blob_agent_manager.set_agent_status(agent_id, status)
    
    def generate_azure_container_name(self, agent_id: str) -> str:
        """Generate Azure-compliant container name for agent"""
        return self.blob_agent_manager.generate_azure_container_name(agent_id)

# User authentication and authorization
class UserManager:
    """Manages user authentication and authorization - now using blob storage"""
    
    def __init__(self):
        self.blob_user_manager = BlobStorageUserManager(AzureConfig())
    
    def authenticate_admin(self, username: str, password: str) -> bool:
        """Authenticate admin user"""
        return self.blob_user_manager.authenticate_admin(username, password)
    
    def authenticate_azure_user(self, username: str, password: str) -> Dict:
        """Authenticate Azure user using Azure AD"""
        return self.blob_user_manager.authenticate_azure_user(username, password)
    
    def get_user_permissions(self, username: str) -> Dict:
        """Get user permissions"""
        return self.blob_user_manager.get_user_permissions(username)
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        return self.blob_user_manager.get_user(username)
    
    def has_permission(self, username: str, agent_id: str, permission_type: str) -> bool:
        """Check if user has specific permission for agent"""
        return self.blob_user_manager.has_permission(username, agent_id, permission_type)
    
    def add_user(self, username: str, role: str, password: str, permissions: List[str] = None) -> bool:
        """Add a new user with explicit password requirement"""
        return self.blob_user_manager.add_user(username, role, password, permissions or [])
    
    def update_user_permissions(self, username: str, permissions: List[str]) -> bool:
        """Update user permissions"""
        return self.blob_user_manager.update_user_permissions(username, permissions)
    
    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        return self.blob_user_manager.delete_user(username)
    
    def get_all_users(self) -> Dict[str, Dict]:
        """Get all users"""
        return self.blob_user_manager.get_all_users()

# Document processing utilities
class DocumentProcessor:
    """Process and extract text from various document formats"""
    
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """Extract text from PDF file"""
        libs = load_heavy_libraries()
        if 'PyPDF2' not in libs:
            return "PDF processing not available. Please install PyPDF2."
        
        try:
            pdf_reader = libs['PyPDF2'].PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            return f"Error processing PDF: {str(e)}"
    
    @staticmethod
    def extract_text_from_docx(file_content: bytes) -> str:
        """Extract text from DOCX file"""
        libs = load_heavy_libraries()
        if 'docx' not in libs:
            return "DOCX processing not available. Please install python-docx."
        
        try:
            doc = libs['docx'].Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            return f"Error processing DOCX: {str(e)}"
    
    @staticmethod
    def extract_text_from_txt(file_content: bytes) -> str:
        """Extract text from TXT file"""
        try:
            return file_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return file_content.decode('latin-1')
            except Exception as e:
                return f"Error processing TXT: {str(e)}"

# Initialize session state
def initialize_session_state():
    """Initialize all session state variables"""
    
    # Initialize Azure config and agent manager
    if AZURE_AVAILABLE:
        try:
            azure_config = AzureConfig()
            agent_manager = AgentManager(azure_config)
            agents = agent_manager.get_active_agents()
            
            # Safety check: ensure agents is always a dictionary
            if not isinstance(agents, dict):
                agents = {}
            
            logger.info("Azure services initialized successfully")
        except Exception as e:
            logger.warning(f"Error initializing Azure services: {e}")
            agents = {}
    else:
        # Azure not available - create demo agents
        agents = {
            'demo_agent': {
                'id': 'demo_agent',
                'name': 'Demo Agent',
                'icon': '🤖',
                'description': 'Demo agent for testing (Azure services not available)',
                'color': '#1e40af 0%, #1e3a8a 100%',
                'container_name': 'demo-documents',
                'categories': ['demo'],
                'connection_string': '',
                'agent_id': 'demo_agent',
                'search_index': 'demo-index',
                'enabled': True
            }
        }
        logger.info("Using demo mode - Azure utilities not available")
    
    # Try to load backup configuration if no agents found
    if not agents:
        backup_path = "config_backup/agent_configs.json"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    all_agents = json.load(f)
                # Filter enabled agents and ensure all required fields
                agents = {}
                for agent_id, config in all_agents.items():
                    if config.get('enabled', True):
                        # Ensure all required fields with defaults
                        agents[agent_id] = {
                            'id': agent_id,
                            'name': config.get('name', agent_id),
                            'icon': config.get('icon', '🤖'),
                            'description': config.get('description', 'No description available'),
                            'color': config.get('gradient', '#1e40af 0%, #1e3a8a 100%'),
                            'container_name': config.get('container', f'{agent_id}-documents'),
                            'categories': config.get('categories', ['general']),
                            'connection_string': config.get('connection_string', ''),
                            'agent_id': config.get('agent_id', ''),
                            'search_index': config.get('search_index', f'{agent_id}-index'),
                            'enabled': config.get('enabled', True)
                        }
                logger.info("Loaded backup agent configurations")
            except Exception as backup_error:
                logger.warning(f"Error loading backup config: {backup_error}")
                agents = {}
    
    # Initialize UserManager
    try:
        user_manager = UserManager() if AZURE_AVAILABLE else None
    except Exception as e:
        logger.warning(f"Error initializing UserManager: {e}")
        user_manager = None
    
    session_vars = {
        "authenticated": False,  # Require proper authentication
        "current_user": None,  # No default user - must login
        "user_role": None,  # No default role - must authenticate
        "current_page": "login",  # Start with login page
        "selected_agent": None,
        "messages": {},  # Agent-specific message history
        "thread_ids": {},  # Agent-specific thread IDs
        "ai_clients": {},  # Agent-specific AI clients
        "connection_status": {},  # Agent-specific connection status
        "user_permissions": {},  # No default permissions - must authenticate
        "agents": agents,
        "user_manager": user_manager
    }
    
    for key, default_value in session_vars.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def show_company_header():
    """Display company logo and header"""
    try:
        # Show Azure status
        if not AZURE_AVAILABLE:
            st.warning("⚠️ Azure services not available - running in demo mode. Some features may be limited.")
        
        # Check if logo file exists
        logo_path = os.path.join(os.path.dirname(__file__), 'ege_kimya.jpg')
        if os.path.exists(logo_path):
            # Create header with logo
            st.markdown("""
            <div class="logo-header">
                <img src="data:image/jpeg;base64,{}" class="company-logo">
                <div>
                    <h1 class="company-title">EGEnts AI Platform</h1>
                    <p class="company-subtitle">Gelişmiş Yapay Zeka Dokuman Yönetim Sistemi</p>
                </div>
            </div>
            """.format(get_base64_of_image(logo_path)), unsafe_allow_html=True)
        else:
            # Fallback header without logo
            st.markdown('<h1 class="main-header">EGEnts AI Platform</h1>', unsafe_allow_html=True)
    except Exception as e:
        # Fallback header on error
        st.markdown('<h1 class="main-header">EGEnts AI Platform</h1>', unsafe_allow_html=True)

def get_base64_of_image(path):
    """Convert image to base64 string for embedding in HTML"""
    import base64
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

def main():
    """Main application entry point"""
    
    try:
        initialize_session_state()
    except Exception as e:
        st.error(f"Initialization error: {e}")
        return
    
    # Import UI components
    try:
        from ui_components import (
            show_login_page, show_dashboard, show_agent_interface, 
            show_settings
        )
    except Exception as e:
        st.error(f"Import error: {e}")
        return
    
    # Display company header with logo only when authenticated
    if st.session_state.get("authenticated", False):
        show_company_header()
    
    # Route based on current page with authentication checks
    try:
        # Always show login page if not authenticated
        if not st.session_state.get("authenticated", False):
            st.session_state.current_page = "login"
            show_login_page()
        # If authenticated, route to requested page
        elif st.session_state.current_page == "login":
            # If already authenticated and on login page, redirect to dashboard
            st.session_state.current_page = "dashboard"
            st.rerun()
        elif st.session_state.current_page == "dashboard":
            show_dashboard()
        elif st.session_state.current_page == "agent_interface":
            show_agent_interface()
        elif st.session_state.current_page == "azure_agent_interface":  # Add this route for consistency
            show_agent_interface()
        elif st.session_state.current_page == "settings":
            # Settings page requires admin role
            if st.session_state.get("user_role") == "admin":
                show_settings()
            else:
                st.error("⚠️ Admin access required for settings")
                if st.button("🏠 Back to Dashboard"):
                    st.session_state.current_page = "dashboard"
                    st.rerun()
        else:
            st.error(f"Unknown page: {st.session_state.current_page}")
        
    except Exception as e:
        st.error(f"Page rendering error: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        st.code(str(e))
