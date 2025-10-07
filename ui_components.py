"""
UI Components for Multi-Agent Azure AI Platform
Contains all the user interface functions and components
"""

import streamlit as st
import pandas as pd
import os
import json
import requests
import msal
import time
import logging
import hashlib
from datetime import datetime
from typing import Dict, List
from functools import lru_cache

# Configure logging
logger = logging.getLogger(__name__)

def generate_response_hash(content: str, agent_id: str, user_input: str) -> str:
    """Generate a unique hash for a response to prevent duplicates"""
    # Only include content and user_input for exact duplicate detection
    # Removed agent_id and timestamp to allow same response for different contexts
    combined = f"{user_input.strip().lower()}_{content[:200]}"  # Use first 200 chars of content
    return hashlib.md5(combined.encode()).hexdigest()

def is_duplicate_response(content: str, agent_id: str, user_input: str) -> bool:
    """Check if this response is a duplicate of a recent response for the EXACT same user input"""
    if 'response_hashes' not in st.session_state:
        st.session_state.response_hashes = {}
    
    # Normalize user input for comparison
    normalized_input = user_input.strip().lower()
    
    # Check against recent responses for this agent
    agent_responses = st.session_state.response_hashes.get(agent_id, {})
    
    # Only consider it duplicate if EXACT same input produces EXACT same content
    stored_content = agent_responses.get(normalized_input)
    if stored_content and stored_content[:200] == content[:200]:
        return True
    
    return False

def register_response(content: str, agent_id: str, user_input: str):
    """Register a new response to track duplicates"""
    if 'response_hashes' not in st.session_state:
        st.session_state.response_hashes = {}
    
    if agent_id not in st.session_state.response_hashes:
        st.session_state.response_hashes[agent_id] = {}
    
    # Store content by normalized input key
    normalized_input = user_input.strip().lower()
    st.session_state.response_hashes[agent_id][normalized_input] = content
    
    # Keep only last 20 input-response pairs to prevent memory bloat
    if len(st.session_state.response_hashes[agent_id]) > 20:
        # Remove oldest entries (keep most recent 20)
        items = list(st.session_state.response_hashes[agent_id].items())
        st.session_state.response_hashes[agent_id] = dict(items[-20:])

def clear_agent_context(agent_id: str):
    """Clear all context and caches for a specific agent"""
    # Clear response hashes
    if 'response_hashes' in st.session_state:
        st.session_state.response_hashes.pop(agent_id, None)
    
    # Clear message caches - more comprehensive cleanup
    cache_keys_to_remove = []
    for key in list(st.session_state.keys()):
        if (key.startswith(f"user_msg_{agent_id}_") or 
            key.startswith(f"assistant_msg_{agent_id}_")):
            cache_keys_to_remove.append(key)
    
    for key in cache_keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear displayed images tracking
    if 'displayed_images_by_agent' in st.session_state:
        st.session_state.displayed_images_by_agent.pop(agent_id, None)

# Helper functions for company header
@lru_cache(maxsize=1)
def get_base64_of_image(path):
    """Convert image to base64 string for embedding in HTML"""
    import base64
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        return ""

def show_company_header():
    """Display company logo and header"""
    try:
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
        logger.error(f"Error displaying company header: {e}")

# Configuration-based admin users (fallback when user_manager is not available)
ADMIN_USERS = [
    "admin",  # Default admin username
    "administrator@yourdomain.com",  # Add your admin email addresses here
    # Add more admin emails as needed
]

def validate_chart_currency_labels(response_text: str, image_path: str = None) -> str:
    """
    Validate and suggest corrections for Turkish currency chart labels
    """
    if not response_text:
        return response_text
        
    # Check for common Turkish currency labeling issues
    suggestions = []
    
    # Check if response mentions chart creation
    if any(word in response_text.lower() for word in ["grafik", "chart", "görselleştir", "plot"]):
        # Look for potential currency value patterns
        import re
        
        # Pattern for values like 2.5, 2.7, etc. (likely millions)
        million_pattern = r'\b[0-9]\.[0-9]+'
        # Pattern for values like 2500, 2700, etc. (likely thousands)  
        thousand_pattern = r'\b[0-9]{4,}'
        
        has_decimal_values = bool(re.search(million_pattern, response_text))
        has_large_integers = bool(re.search(thousand_pattern, response_text))
        
        if has_decimal_values and "bin tl" in response_text.lower():
            suggestions.append("⚠️ UYARI: Grafikte ondalıklı değerler (2.5, 2.7 gibi) görülüyor ancak y ekseni 'Bin TL' olarak etiketlenmiş. Bu değerler muhtemelen 'Milyon TL' cinsinden olmalı.")
        
        if has_large_integers and "milyon tl" in response_text.lower():
            suggestions.append("⚠️ UYARI: Grafikte büyük tam sayı değerler görülüyor ancak y ekseni 'Milyon TL' olarak etiketlenmiş. Bu değerler muhtemelen 'Bin TL' cinsinden olmalı.")
    
    if suggestions:
        return response_text + "\n\n" + "\n".join(suggestions)
    
    return response_text

def is_admin_user(username: str = None) -> bool:
    """Check if the current user or specified username is an admin"""
    if username is None:
        username = st.session_state.get('current_user', '')
    
    # Check session state role first
    if st.session_state.get('user_role') == 'admin':
        return True
    
    # Check configuration-based admin list
    if username in ADMIN_USERS:
        return True
    
    # Check user_manager if available
    if st.session_state.get('user_manager') and username:
        try:
            user_data = st.session_state.user_manager.get_user(username)
            if user_data and isinstance(user_data, dict):
                return user_data.get('role') == 'admin'
        except Exception:
            pass
    
    return False

def clean_message_content(content: str) -> str:
    """Clean message content from unwanted HTML tags but PRESERVE line structure for readability."""
    import re
    if not isinstance(content, str):
        return str(content)

    # Normalize newlines
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Remove dangerous/script/style tags entirely
    content = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.DOTALL | re.IGNORECASE)

    # Remove message wrapper divs but keep inner text (already removed entirely above; adjust to unwrap)
    content = re.sub(r'<div[^>]*class=["\'][^"\'>]*message[^"\'>]*["\'][^>]*>(.*?)</div>', r'\1', content, flags=re.DOTALL | re.IGNORECASE)

    # Strip all remaining tags but keep line breaks placeholders
    # Replace <br> and <p> with newlines before stripping
    content = re.sub(r'<\s*br\s*/?>', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'</p>', '\n\n', content, flags=re.IGNORECASE)
    content = re.sub(r'<p[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<[^>]+>', '', content)

    # Collapse trailing spaces but keep newlines
    # Remove excessive spaces at line starts/ends
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in content.split('\n')]
    content = '\n'.join(lines)

    # Collapse more than 2 blank lines to exactly one blank line
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Trim overall
    content = content.strip()
    return content

def format_message_with_references(content: str) -> str:
    """Format message content; add document reference styling AND readable paragraphs/lists."""
    import re, html

    if not content:
        return ""

    # Remove leftover wrapper divs (defensive)
    content = re.sub(r'<div[^>]*class=["\']message-(time|bubble)["\'][^>]*>.*?</div>', '', content, flags=re.DOTALL)

    # If already formatted with our span, skip heavy processing but still ensure paragraph wrapping
    already_referenced = '<span class="document-reference">' in content

    # Work on a copy for reference detection (don't escape yet)
    work = content

    # Reference patterns
    reference_pattern1 = r'\[referans:\s*([^\]]+)\]'
    def replace_reference1(m):
        return f'<span class="document-reference">📄 {html.escape(m.group(1).strip())}</span>'
    work = re.sub(reference_pattern1, replace_reference1, work)

    filename_pattern = r'\b[A-Za-z0-9_\-\.öçşğüıÖÇŞĞÜİıİçÇşŞğĞüÜöÖ]+\.(?:pdf|docx|doc|txt|xlsx|xls|ppt|pptx|csv|json|xml)\b'
    filenames = sorted(set(re.findall(filename_pattern, work, re.IGNORECASE)), key=len, reverse=True)
    for fn in filenames:
        if f'📄 {fn}' in work:
            continue
        work = re.sub(r'(?<!\w)'+re.escape(fn)+r'(?!\w)', f'<span class="document-reference">📄 {html.escape(fn)}</span>', work)

    # Now escape remaining HTML (except our spans)
    # Temporarily protect spans
    span_placeholder = '§§SPAN§§'
    protected = []
    def protect_span(m):
        protected.append(m.group(0))
        return f'{span_placeholder}{len(protected)-1}'
    temp = re.sub(r'<span class="document-reference">.*?</span>', protect_span, work)
    temp = html.escape(temp)
    # Restore spans
    for idx, original in enumerate(protected):
        temp = temp.replace(f'{span_placeholder}{idx}', original)

    # Reconstruct structure from preserved newlines
    lines = [ln.strip() for ln in temp.split('\n')]
    # Remove leading/trailing empty lines
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    blocks = []
    current = []
    for ln in lines:
        if not ln:
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(ln)
    if current:
        blocks.append(current)

    html_parts = []
    list_item_pattern = re.compile(r'^[-*•]\s+(.+)')
    ordered_item_pattern = re.compile(r'^(\d+)[\.\)]\s+(.+)')

    for block in blocks:
        # Detect if block is unordered list
        if all(list_item_pattern.match(l) for l in block):
            html_parts.append('<ul>')
            for l in block:
                html_parts.append(f"<li>{list_item_pattern.match(l).group(1)}</li>")
            html_parts.append('</ul>')
            continue
        # Detect ordered list
        if all(ordered_item_pattern.match(l) for l in block):
            html_parts.append('<ol>')
            for l in block:
                m = ordered_item_pattern.match(l)
                html_parts.append(f"<li>{m.group(2)}</li>")
            html_parts.append('</ol>')
            continue
        # Mixed or plain paragraph: keep line breaks inside
        paragraph = '<br>'.join(block)
        html_parts.append(f'<p>{paragraph}</p>')

    formatted = ''.join(html_parts)
    return formatted

def handle_file_download(file_id: str, filename: str, ai_client) -> bool:
    """
    Handle file download from Azure AI Agent
    
    Args:
        file_id: The file ID from Azure AI Agent
        filename: The filename to display/save
        ai_client: The Azure AI Agent client instance
        
    Returns:
        True if download successful, False otherwise
    """
    try:
        if not ai_client:
            st.error("❌ AI client mevcut değil")
            return False
            
        if not hasattr(ai_client, 'download_file_content'):
            st.error("❌ AI client'da download_file_content metodu yok")
            return False
        
        # Show loading message
        with st.spinner(f"📥 {filename} dosyası indiriliyor..."):
            try:
                # Download file content
                file_content = ai_client.download_file_content(file_id)
                
                if file_content is None:
                    st.error(f"❌ {filename} dosyası indirilemedi")
                    return False
                
                if not isinstance(file_content, bytes):
                    st.error(f"❌ {filename} dosyası indirilemedi - Beklenmeyen format")
                    return False
                
                if len(file_content) == 0:
                    st.error(f"❌ {filename} dosyası boş")
                    return False
                
                st.success(f"✅ {filename} dosyası başarıyla indirildi! ({len(file_content)} bytes)")
                
                # Provide download button
                st.download_button(
                    label=f"📁 {filename} - İndir ({len(file_content)} bytes)",
                    data=file_content,
                    file_name=filename,
                    mime="application/octet-stream",
                    key=f"download_{file_id}_{int(time.time())}"
                )
                
                return True
                
            except Exception as download_error:
                st.error(f"❌ İndirme sırasında hata: {str(download_error)}")
                logger.error(f"Download error for {file_id}: {download_error}")
                return False
            
    except Exception as e:
        st.error(f"❌ Dosya indirme hatası: {str(e)}")
        logger.error(f"File download error for {file_id}: {e}")
        return False

def display_downloadable_files(message_content: str, ai_client) -> None:
    """
    Display downloadable files found in message content and recent generated files
    
    Args:
        message_content: The message content to scan for files
        ai_client: The Azure AI Agent client instance
    """
    try:
        if not ai_client:
            return
        
        downloadable_files = []
        
        # Method 1: Get files from message content
        if hasattr(ai_client, 'get_downloadable_files_from_message'):
            content_files = ai_client.get_downloadable_files_from_message(message_content)
            downloadable_files.extend(content_files)
        
        # Method 2: Get recently generated files (more reliable)
        if hasattr(ai_client, 'get_recent_generated_files'):
            # Get the current thread_id from session state
            agent_id = getattr(ai_client, 'agent_id', None)
            
            if agent_id and st.session_state.get('thread_ids'):
                thread_id = st.session_state.thread_ids.get(agent_id)
                
                if thread_id:
                    recent_files = ai_client.get_recent_generated_files(thread_id, limit=5)
                    
                    # Add recent files that aren't already in the list
                    for recent_file in recent_files:
                        existing = any(f['file_id'] == recent_file['file_id'] for f in downloadable_files)
                        if not existing:
                            downloadable_files.append({
                                'file_id': recent_file['file_id'],
                                'filename': recent_file['filename'],
                                'url': f"#download:{recent_file['file_id']}"
                            })
        
        if not downloadable_files:
            return
        
        # Display download section
        st.markdown("---")
        st.markdown("### 📁 İndirilebilir Dosyalar")
        
        # Create columns for better layout
        cols = st.columns(min(len(downloadable_files), 3))
        
        for idx, file_info in enumerate(downloadable_files):
            col_idx = idx % len(cols)
            
            with cols[col_idx]:
                file_id = file_info.get('file_id', '')
                filename = file_info.get('filename', 'Dosya')
                
                st.markdown(f"**📄 {filename}**")
                
                # Try to get file content for direct download
                try:
                    if hasattr(ai_client, 'download_file_content'):
                        # Download file content
                        file_content = ai_client.download_file_content(file_id)
                        
                        if file_content and isinstance(file_content, bytes) and len(file_content) > 0:
                            # Direct download button with unique key
                            import time
                            unique_key = f"direct_download_{file_id}_{idx}_{int(time.time() * 1000)}"
                            st.download_button(
                                label=f"⬇️ {filename} İndir ({len(file_content)} bytes)",
                                data=file_content,
                                file_name=filename,
                                mime="application/octet-stream",
                                key=unique_key,
                                help=f"{filename} dosyasını doğrudan indir"
                            )
                        else:
                            st.error(f"❌ {filename} dosyası indirilemedi")
                    else:
                        st.error("❌ İndirme özelliği mevcut değil")
                        
                except Exception as e:
                    st.error(f"❌ {filename} indirme hatası: {str(e)}")
                
                st.markdown("---")
        
    except Exception as e:
        logger.error(f"Error displaying downloadable files: {e}")
        st.error(f"Dosya listesi gösterilirken hata: {str(e)}")

def process_message_with_download_links(content: str, ai_client) -> str:
    """
    Process message content to convert download references to interactive elements
    
    Args:
        content: Message content with potential download links
        ai_client: Azure AI Agent client for file operations
        
    Returns:
        Processed content with download elements
    """
    try:
        import re
        
        # Look for download link patterns like #download:file_id
        download_pattern = r'#download:([a-zA-Z0-9\-_]+)'
        
        def replace_download_link(match):
            file_id = match.group(1)
            return f'<button onclick="downloadFile(\'{file_id}\')" class="download-btn">📥 İndir</button>'
        
        # Replace download links
        processed_content = re.sub(download_pattern, replace_download_link, content)
        
        return processed_content
        
    except Exception as e:
        logger.error(f"Error processing download links: {e}")
        return content

# Corporate process icons for agent selection
CORPORATE_ICONS = {
    "📊": "İstatistik & Raporlama",
    "📈": "Satış & Büyüme", 
    "📋": "Proje Yönetimi",
    "⚖️": "Hukuk & Uyumluluk",
    "💼": "İş Geliştirme",
    "🏭": "Üretim & Operasyon",
    "🔧": "Teknik Destek",
    "👥": "İnsan Kaynakları",
    "💰": "Finans & Muhasebe",
    "📦": "Tedarik Zinciri",
    "🎯": "Kalite Yönetimi",
    "🌐": "IT & Teknoloji",
    "📢": "Pazarlama & İletişim",
    "🛡️": "Güvenlik & Risk",
    "🔍": "Araştırma & Geliştirme",
    "📚": "Eğitim & Geliştirme",
    "🏢": "Kurumsal Yönetim",
    "📞": "Müşteri Hizmetleri",
    "📄": "Dokümantasyon",
    "⚙️": "Sistem Yönetimi"
}

def show_icon_selector(default_icon: str = "🤖", key: str = "icon_selector", use_radio: bool = False) -> str:
    """Display an icon selector with corporate process icons (form-compatible)"""
    st.write("**🎯 Ajan İkonu Seçin:**")
    st.write("*Kurumsal süreçlere uygun ikonlar arasından seçim yapın:*")
    
    # Create options for selectbox/radio (icon + description)
    icon_options = []
    icon_mapping = {}
    
    for icon, description in CORPORATE_ICONS.items():
        option_text = f"{icon} - {description}"
        icon_options.append(option_text)
        icon_mapping[option_text] = icon
    
    # Find current selection index
    current_selection_text = None
    for option_text, icon in icon_mapping.items():
        if icon == default_icon:
            current_selection_text = option_text
            break
    
    # If default icon not in predefined list, add it as custom option
    if current_selection_text is None:
        custom_option = f"{default_icon} - Özel İkon"
        icon_options.insert(0, custom_option)
        icon_mapping[custom_option] = default_icon
        current_selection_text = custom_option
    
    # Choose input method based on parameter
    if use_radio:
        # Use radio buttons (better for forms, more visual)
        selected_option = st.radio(
            "İkon Seçin:",
            options=icon_options,
            index=icon_options.index(current_selection_text) if current_selection_text in icon_options else 0,
            key=f"{key}_radio",
            help="Kurumsal süreçlere uygun ikonlar arasından seçim yapın",
            horizontal=False
        )
    else:
        # Use selectbox (more compact)
        selected_option = st.selectbox(
            "İkon Seçin:",
            options=icon_options,
            index=icon_options.index(current_selection_text) if current_selection_text in icon_options else 0,
            key=f"{key}_selectbox",
            help="Kurumsal süreçlere uygun ikonlar arasından seçim yapın"
        )
    
    # Get the selected icon
    selected_icon = icon_mapping.get(selected_option, default_icon)
    
    # Display selected icon preview
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); 
                border-radius: 10px; padding: 1rem; margin: 1rem 0; 
                border-left: 4px solid #2196f3; text-align: center;'>
        <h3>Seçili İkon: {selected_icon}</h3>
        <p><em>{selected_option.split(' - ')[1] if ' - ' in selected_option else 'Özel İkon'}</em></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Also allow manual entry for custom icons (when not inside an expander)
    manual_icon = st.text_input("🔧 Özel İkon (İsteğe Bağlı):", 
                               value=selected_icon, 
                               key=f"{key}_manual",
                               help="İstediğiniz emoji'yi buraya yazabilirsiniz (örn: 🚀, 💡, ⭐)")
    if manual_icon and manual_icon != selected_icon:
        selected_icon = manual_icon
    
    return selected_icon

def show_login_page():
    """Display the login page with two authentication options"""
    
    # Show company header with logo
    show_company_header()
    
    # Login container
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Login method selection
        login_method = st.radio(
            "Choose login method:",
            ["🔑 Admin Login", "☁️ Azure User Login"],
            index=1,  # Default to Azure User Login (index 1)
            horizontal=True
        )
        
        # Login forms
        if login_method == "🔑 Admin Login":
            with st.form("admin_login"):
                st.subheader("Admin Login")
                username = st.text_input("Username", placeholder="admin")
                password = st.text_input("Password", type="password", placeholder="Password")
                
                submitted = st.form_submit_button("Login as Admin", type="primary")
                
                if submitted:
                    if not st.session_state.user_manager:
                        st.error("❌ User management system is not available. Please contact administrator.")
                    elif st.session_state.user_manager.authenticate_admin(username, password):
                        st.session_state.authenticated = True
                        st.session_state.current_user = username
                        st.session_state.user_role = "admin"
                        st.session_state.current_page = "dashboard"
                        st.success("✅ Admin login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid admin credentials")
        
        else:  # Azure User Login
            # MFA destekli Azure AD Login (OAuth2 Authorization Code Flow)
            st.subheader("Azure AD Login (MFA Destekli)")

            # MSAL ayarları - environment variables'dan al
            import msal
            import requests
            import os
            import urllib.parse

            # Azure Web App environment'da bu değerler Application Settings'de olmalı
            CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
            TENANT_ID = os.environ.get("AZURE_TENANT_ID")
            CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

            # Eksik kritik değişken kontrolü
            missing = [k for k,v in {"AZURE_CLIENT_ID":CLIENT_ID, "AZURE_TENANT_ID":TENANT_ID, "AZURE_CLIENT_SECRET":CLIENT_SECRET}.items() if not v]
            if missing:
                st.error(f"Eksik ortam değişkenleri: {', '.join(missing)} - Azure AD login çalışmayacak.")

            # Redirect URI'yi dinamik olarak belirle (önce REDIRECT_URI env, yoksa site adından üret, lokal fallback)
            env_redirect = os.environ.get("REDIRECT_URI")
            if env_redirect:
                REDIRECT_URI = env_redirect.rstrip('/') + '/'
            elif "WEBSITE_SITE_NAME" in os.environ:
                # Bölge domain'i değişebilir, sadece site adını kullanıp REDIRECT_URI yoksa varsayım yapıyoruz
                site = os.environ.get("WEBSITE_SITE_NAME")
                # Eğer tam domain zaten REDIRECT_HOST olarak verilmişse ileride geliştirilebilir
                REDIRECT_URI = f"https://{site}.westeurope-01.azurewebsites.net/"
            else:
                REDIRECT_URI = "http://localhost:8502/"

            # (Bilgi metni ve redirect URI satırı kullanıcı isteğiyle kaldırıldı)
            
            AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
            SCOPE = ["User.Read"]

            try:
                app = msal.ConfidentialClientApplication(
                    CLIENT_ID,
                    authority=AUTHORITY,
                    client_credential=CLIENT_SECRET
                )

                # Login URL oluştur
                auth_url = app.get_authorization_request_url(
                    SCOPE,
                    redirect_uri=REDIRECT_URI
                )
                st.markdown(f"[Microsoft ile Giriş Yap]({auth_url})")

                # Callback: URL'de kod varsa token al
                query_params = st.query_params
                if "code" in query_params:
                    code = query_params["code"]
                    result = app.acquire_token_by_authorization_code(
                        code,
                        scopes=SCOPE,
                        redirect_uri=REDIRECT_URI
                    )
                    if "access_token" in result:
                        user = requests.get(
                            "https://graph.microsoft.com/v1.0/me",
                            headers={"Authorization": f"Bearer {result['access_token']}"}
                        ).json()
                        
                        user_email = user.get("userPrincipalName", user.get("mail", ""))
                        
                        # Check if user_manager is available before setting user info
                        if not st.session_state.user_manager:
                            # Fallback: Check if user is in ADMIN_USERS configuration
                            if user_email in ADMIN_USERS:
                                user_role = "admin"
                                st.info(f"✅ Admin access granted via configuration (user_manager unavailable)")
                            else:
                                user_role = "standard"
                                st.warning(f"⚠️ User management system unavailable. Limited access granted.")
                        else:
                            # Check if the Azure user is registered in the system and get their role
                            user_data = st.session_state.user_manager.get_user(user_email)
                            if user_data and isinstance(user_data, dict):
                                # User exists in system, use their assigned role
                                user_role = user_data.get('role', 'standard')
                            else:
                                # New Azure user, check fallback admin list
                                if user_email in ADMIN_USERS:
                                    user_role = "admin"
                                    st.info(f"✅ Admin access granted via configuration")
                                else:
                                    user_role = 'standard'
                                    st.info(f"ℹ️ New Azure user detected. Contact administrator for permission setup.")
                        
                        st.session_state.authenticated = True
                        st.session_state.current_user = user_email
                        st.session_state.user_role = user_role  # Use the determined role
                        st.session_state.current_page = "dashboard"
                        st.session_state.token = result
                        st.success(f"✅ Azure AD girişi başarılı! Role: {user_role}")
                        st.rerun()
                    else:
                        st.error("Giriş başarısız: " + str(result.get("error_description", "Bilinmeyen hata")))
            except Exception as e:
                st.error(f"❌ Azure AD authentication hatası: {str(e)}")

def show_dashboard():
    """Display the main dashboard with agent selection"""
    
    # Force session state agents to be a dictionary if it's not
    if "agents" in st.session_state and not isinstance(st.session_state.agents, dict):
        st.warning(f"⚠️ Resetting invalid agents data from session state (was {type(st.session_state.agents)})")
        st.session_state.agents = {}
    
    # Clean up any orphaned schedule-related session state items
    orphaned_keys = [key for key in st.session_state.keys() 
                     if any(pattern in key for pattern in ['schedule', 'period', 'weekday', 'hour', 'minute', 'job_'])]
    if orphaned_keys:
        for key in orphaned_keys:
            if key.startswith(('job_schedule_', 'job_period_', 'job_weekday_', 'job_hour_', 'job_minute_')):
                continue  # Keep valid job-related keys
            del st.session_state[key]
    
    # Header with logout
    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        st.markdown('<h1 class="main-header"></h1>', 
                    unsafe_allow_html=True)
    with col2:
        if st.session_state.user_role == "admin":
            if st.button("⚙️ Settings"):
                st.session_state.current_page = "settings"
                st.rerun()
    with col3:
        if st.button("🚪 Logout"):
            # Reset session state
            for key in list(st.session_state.keys()):
                if key not in ['agents', 'user_manager']:
                    del st.session_state[key]
            st.session_state.current_page = "login"
            st.rerun()
    
    # User info with permission status
    user_info = f"👋 Welcome {st.session_state.current_user} ({st.session_state.user_role})"
    if is_admin_user():
        user_info += " - 🔑 Admin Access"
    st.info(user_info)
    
    # Show warning if user_manager is not available
    if not st.session_state.user_manager and st.session_state.user_role != "admin":
        st.warning("⚠️ User management system is not available. Access to agents may be limited.")
    
    # Agent grid
    st.subheader("🤖 Available AI Agents")
    
    # Use agents from session state (loaded from configuration)
    agents = st.session_state.get("agents", {})
    agents_source = "agent configuration"
    
    try:
        # Only try blob storage if no agents in session state
        if not agents:
            cached_manager = st.session_state.get('agent_manager')
            if cached_manager:
                try:
                    agents = cached_manager.get_active_agents()
                    agents_source = "cached agent manager"
                except Exception:
                    agents = {}
        
        if not agents:
            from azure_utils import AzureConfig, BlobStorageAgentManager
            # Initialize without any extra parameters
            blob_agent_manager = BlobStorageAgentManager(AzureConfig())
            blob_agents = blob_agent_manager.get_active_agents()  # Only show active agents
            
            if blob_agents:
                agents = blob_agents
                agents_source = "blob storage"
        
        # If still no agents from blob storage, try backup configuration
        if not agents:
            backup_path = "config_backup/agent_configs.json"
            if os.path.exists(backup_path):
                import json
                with open(backup_path, 'r', encoding='utf-8') as f:
                    all_agents = json.load(f)
                # Filter only enabled agents and ensure all required fields
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
                            'enabled': config.get('enabled', True),
                            'status': config.get('status', 'active'),
                            'agent_type': config.get('agent_type', 'Data Agent'),
                            'data_container': config.get('data_container', ''),
                            'data_file': config.get('data_file', '')
                        }
                agents_source = "backup configuration"
        
        # Always update session state with fresh data
        st.session_state.agents = agents
        
    except Exception as e:
        # Try to use existing session state as fallback
        agents = st.session_state.get("agents", {})
        agents_source = "session cache"
        
        # If still no agents, try backup configuration as final fallback
        if not agents:
            backup_path = "config_backup/agent_configs.json"
            if os.path.exists(backup_path):
                try:
                    import json
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        all_agents = json.load(f)
                    # Filter only enabled agents and ensure all required fields
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
                                'enabled': config.get('enabled', True),
                                'status': config.get('status', 'active'),
                                'agent_type': config.get('agent_type', 'Data Agent'),
                                'data_container': config.get('data_container', ''),
                                'data_file': config.get('data_file', '')
                            }
                    st.session_state.agents = agents
                    agents_source = "fallback backup configuration"
                    st.info(f"📂 Fallback: Loaded {len(agents)} agents from backup configuration")
                except Exception as backup_error:
                    st.error(f"Error loading backup configuration: {backup_error}")
                    agents = {}
    
    # Safety check: ensure agents is always a dictionary
    if not isinstance(agents, dict):
        st.error(f"Invalid agents data format. Expected dict, got {type(agents)}. Resetting to empty dictionary.")
        st.error(f"Agent data content: {agents}")
        agents = {}
        st.session_state.agents = agents
    
    if not agents:
        st.warning("⚠️ No agents to display!")
        return
    
    cols = st.columns(3)
    
    for idx, (agent_id, agent_config) in enumerate(agents.items()):
        col = cols[idx % 3]
        
        with col:
            # Check permissions - require user_manager unless admin
            if st.session_state.user_role == "admin":
                has_access = True
            elif not st.session_state.user_manager:
                # If user_manager is None, only admin can access
                has_access = False
            elif not st.session_state.current_user:
                # If no current user, no access
                has_access = False
            else:
                # Check actual permissions
                has_access = st.session_state.user_manager.has_permission(
                    st.session_state.current_user, agent_id, "access")
            
            # Agent card
            card_style = "agent-card" if has_access else "agent-card" + " opacity: 0.5;"
            
            st.markdown(f"""
            <div class="{card_style}" style="border-color: {agent_config['color']};">
                <div class="agent-icon">{agent_config['icon']}</div>
                <div class="agent-title">{agent_config['name']}</div>
                <div class="agent-description">{agent_config['description']}</div>
                <div class="agent-stats">
                    <small>
                        📁 Container: {agent_config['container_name']}<br>
                         Categories: {', '.join(agent_config['categories'])}
                    </small>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if has_access:
                if st.button(f"Open {agent_config['name']}", key=f"open_{agent_id}", type="primary"):
                    st.session_state.selected_agent = agent_id
                    st.session_state.current_page = "agent_interface"
                    st.rerun()
            else:
                st.warning("⚠️ No access permission")

def show_agent_interface():
    """Display the agent interface with chat and document management"""
    
    if not st.session_state.selected_agent:
        st.error("No agent selected")
        return
    
    # Safely get agents from session state
    agents = st.session_state.get("agents", {})
    if not isinstance(agents, dict) or st.session_state.selected_agent not in agents:
        st.error("Selected agent not found in configuration")
        if st.button("🏠 Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.rerun()
        return
    
    agent_config = agents[st.session_state.selected_agent]
    agent_id = st.session_state.selected_agent
    
    # *** IMPORTANT: Check access permission before allowing entry to agent interface ***
    if st.session_state.user_role == "admin":
        has_access = True
    elif not st.session_state.user_manager:
        # If user_manager is None, only admin can access
        has_access = False
    elif not st.session_state.current_user:
        # If no current user, no access
        has_access = False
    else:
        # Check actual permissions
        has_access = st.session_state.user_manager.has_permission(
            st.session_state.current_user, agent_id, "access")
    
    if not has_access:
        st.error("🚫 Access Denied: You don't have permission to access this agent")
        st.warning("⚠️ Please contact your administrator to request access permissions.")
        if st.button("🏠 Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.rerun()
        return
    
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
        <div style="font-size: 1.5rem; text-align: left; margin-bottom: 1rem; font-weight: bold; color: #333;">
            {agent_config['icon']} {agent_config['name']}
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("🏠 Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    st.markdown(f"**Description:** {agent_config['description']}")
    
    # Tab navigation
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📁 Documents", "⚙️ Settings"])
    
    with tab1:
        show_agent_chat(agent_config)
    
    with tab2:
        show_document_management(agent_config)
    
    with tab3:
        show_agent_settings(agent_config)

def show_agent_chat(agent_config: Dict):
    """Display the chat interface for the selected agent"""
    
    # Use the same agent_id as used for access permission check in show_agent_interface
    # This ensures consistency between access and chat permission checks
    permission_agent_id = st.session_state.selected_agent
    
    # Dinamik agent id: env > agent_config > session fallback (for Azure AI connection only)
    import os
    env_agent_id = os.getenv("AZURE_AI_AGENT_ID")
    azure_agent_id = env_agent_id or agent_config.get('agent_id') or agent_config.get('id')
    agent_config['resolved_agent_id'] = azure_agent_id
    
    # Check permissions first - before any connection attempts
    # Use permission_agent_id for consistency with access permission check
    if st.session_state.user_role == "admin":
        can_chat = True
    elif not st.session_state.user_manager:
        can_chat = False
    elif not st.session_state.current_user:
        can_chat = False
    else:
        can_chat = st.session_state.user_manager.has_permission(
            st.session_state.current_user, permission_agent_id, "chat")
    
    if not can_chat:
        st.error("🚫 Chat Access Denied: You don't have chat permission for this agent")
        st.warning("⚠️ Please contact your administrator to request chat permissions.")
        return

    # Initialize agent client if needed (only after permission check)
    # Use azure_agent_id for Azure AI connection, permission_agent_id for session keys
    if azure_agent_id not in st.session_state.ai_clients:
        try:
            with st.spinner("🔄 Connecting to Azure AI Foundry agent..."):
                from azure_utils import EnhancedAzureAIAgentClient, AzureConfig
                
                config = AzureConfig()
                
                # Get connection details from agent config
                connection_string = agent_config.get('connection_string', '')
                configured_agent_id = agent_config.get('resolved_agent_id', '')
                container_name = agent_config.get('container_name', '')
                
                # Create client with connection details and container name for document references
                try:
                    client = EnhancedAzureAIAgentClient(
                        connection_string,
                        configured_agent_id,
                        config,
                        container_name  # Pass container name for document reference processing
                    )
                except Exception as client_error:
                    st.error(f"❌ Client creation failed: {str(client_error)}")
                    return
                
                # Determine agent type (used internally, no UI banner)
                agent_type = agent_config.get('agent_type', 'Data Agent')
                
                if agent_type == 'Data Analyzer':
                    # Create code interpreter agent with data file
                    data_container = agent_config.get('data_container', '')
                    data_file = agent_config.get('data_file', '')
                    
                    if not data_container or not data_file:
                        data_container = None
                        data_file = None
                    
                    # Removed the initialization banner to avoid showing the highlighted message
                    
                    # Create code interpreter agent with or without data file
                    if data_file and data_container:
                        instructions = f"""You are a data analysis assistant specialized in analyzing the file '{data_file}'. 
                        You have access to this data file and can perform comprehensive data analysis, create visualizations, and answer questions about the data. 
                        
                        Key capabilities:
                        - Load and examine the data file structure
                        - Perform statistical analysis
                        - Create charts and visualizations  
                        - Answer specific questions about the data
                        - Generate insights and recommendations
                        
                        Always start by examining the available data file and provide clear explanations with your analysis."""
                    else:
                        instructions = """You are a data analysis assistant with code interpreter capabilities. 
                        While no specific data file is currently attached, you can still help with:
                        
                        - Data analysis code and guidance
                        - Creating sample data for demonstrations
                        - Statistical analysis explanations
                        - Visualization examples
                        - General data science questions
                        
                        **IMPORTANT: This Data Analyzer agent has been configured to work with scheduled jobs. 
                        File management (uploading data files to code interpreter) is now handled by background jobs 
                        configured in the Agent Configuration section. The agent is ready for analysis with files 
                        provided by the job system.**
                        """
                    
                    # For Data Analyzer agents, we no longer automatically load files
                    # Files will be managed by the Job system
                
                # Try to create thread
                try:
                    thread = client.create_thread()
                    
                    # Check if thread was created successfully
                    if thread and hasattr(thread, 'id'):
                        thread_id = thread.id
                        connection_status = True
                        
                        st.session_state.ai_clients[azure_agent_id] = client
                        st.session_state.thread_ids[azure_agent_id] = thread_id
                        st.session_state.connection_status[azure_agent_id] = connection_status
                        
                        if azure_agent_id not in st.session_state.messages:
                            st.session_state.messages[azure_agent_id] = []
                    else:
                        st.error("❌ Thread creation failed")
                        return
                        
                except Exception as thread_error:
                    st.error(f"❌ Thread creation failed: {str(thread_error)}")
                    return
                
        except Exception as e:
            st.error(f"❌ Connection Failed: {str(e)}")
            return
    
    # Check connection status
    connection_status = st.session_state.connection_status.get(azure_agent_id, False)
    if not connection_status:
        st.error("❌ Azure AI Foundry connection required")
        return
    
    # Display chat container and place control buttons at the very top
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    # Top controls (moved here from bottom per request)
    top_col1, top_col2 = st.columns([1,1])
    with top_col1:
        if st.button("🔄 New Conversation", key=f"new_conv_top_{azure_agent_id}"):
            # Complete conversation reset for this agent
            try:
                # 1. Clear all agent context and caches (new function)
                clear_agent_context(azure_agent_id)
                
                # 2. Reset in-memory chat history for this agent completely
                st.session_state.messages[azure_agent_id] = []
                
                # 3. Reset displayed images tracking for this agent
                if 'displayed_images_by_agent' not in st.session_state:
                    st.session_state.displayed_images_by_agent = {}
                st.session_state.displayed_images_by_agent[azure_agent_id] = set()
                
                # 4. Generate new conversation ID for complete isolation
                import uuid
                new_conversation_id = str(uuid.uuid4())
                if 'conversation_ids' not in st.session_state:
                    st.session_state.conversation_ids = {}
                st.session_state.conversation_ids[azure_agent_id] = new_conversation_id
                
                # 5. Create a brand new backend thread for complete isolation
                if azure_agent_id in st.session_state.ai_clients:
                    client = st.session_state.ai_clients[azure_agent_id]
                    try:
                        new_thread = client.create_thread()
                        if new_thread and hasattr(new_thread, 'id'):
                            # Update to new thread ID
                            st.session_state.thread_ids[azure_agent_id] = new_thread.id
                            st.success("✅ Yeni konuşma başlatıldı!")
                        else:
                            st.error("❌ Yeni konuşma oluşturulamadı")
                    except Exception as thread_error:
                        st.error(f"❌ Thread oluşturma hatası: {str(thread_error)}")
                
                # Force immediate refresh
                st.rerun()
                
            except Exception as reset_error:
                st.error(f"❌ Konuşma sıfırlama hatası: {str(reset_error)}")
    # Small italic warning placed under the New Conversation button (left column)
    st.markdown("""
    <div style="font-size:0.85rem; color:#c62828; font-style:italic; margin-top:10px;">
    Önemli Uyarı: “Bu yapay zekâ aracının ürettiği yanıtlar her zaman kesin doğruluk taşımayabilir. Kullanıcıların elde edilen bilgileri kendi değerlendirmeleriyle doğrulamaları tavsiye edilir.”
    </div>
    """, unsafe_allow_html=True)
    with top_col2:
        if st.button("💾 Export Chat", key=f"export_top_{azure_agent_id}"):
            if azure_agent_id in st.session_state.messages:
                chat_export = ""
                for msg in st.session_state.messages[azure_agent_id]:
                    role = "You" if msg["role"] == "user" else agent_config['name']
                    chat_export += f"{role}: {msg['content']}\n\n"
                st.download_button(
                    label="📥 Download Chat",
                    data=chat_export,
                    file_name=f"{agent_config['name']}_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    key=f"download_top_{azure_agent_id}"
                )
    st.markdown("---")

    agent_messages = st.session_state.messages.get(azure_agent_id, [])
    # Only render messages that belong to the current thread AND conversation for this agent
    current_thread_id = st.session_state.thread_ids.get(azure_agent_id)
    current_conversation_id = st.session_state.get('conversation_ids', {}).get(azure_agent_id)
    
    # Enhanced filtering: ensure we only show messages for current thread AND conversation
    # This provides double isolation to prevent any message bleeding between conversations
    filtered_messages = []
    if current_thread_id and agent_messages:
        for m in agent_messages:
            msg_thread_id = m.get('thread_id')
            msg_conversation_id = m.get('conversation_id')
            
            # Only include messages that match both thread_id and conversation_id
            # If no conversation_id in message (old messages), only match thread_id
            if msg_thread_id == current_thread_id:
                if current_conversation_id:
                    # If we have a current conversation ID, only show messages from this conversation
                    if msg_conversation_id == current_conversation_id:
                        filtered_messages.append(m)
                else:
                    # If no current conversation ID, show messages without conversation ID (backward compatibility)
                    if not msg_conversation_id:
                        filtered_messages.append(m)
    
    # Additional safety: if we have no thread_id but have messages, 
    # it might be a new conversation - start fresh
    if not current_thread_id and agent_messages:
        st.session_state.messages[azure_agent_id] = []
        filtered_messages = []
    for i, message in enumerate(filtered_messages):
        message_time = datetime.now().strftime("%H:%M")
        
        # Clean the message content from any unwanted HTML
        clean_content = clean_message_content(message["content"])
        
        if message["role"] == "user":
            # Use improved caching for user messages with conversation context
            msg_timestamp = message.get('timestamp', '')
            cache_key = f"user_msg_{azure_agent_id}_{current_conversation_id}_{i}_{hash(clean_content + msg_timestamp)}"
            if cache_key not in st.session_state:
                st.session_state[cache_key] = format_message_with_references(clean_content)
            formatted_content = st.session_state[cache_key]
            
            st.markdown(f"""
            <div class="message-bubble user-message">
                {formatted_content}
                <div class="message-time">{message_time}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Use improved caching for assistant messages with conversation context
            msg_timestamp = message.get('timestamp', '')
            cache_key = f"assistant_msg_{azure_agent_id}_{current_conversation_id}_{i}_{hash(clean_content + msg_timestamp)}"
            if cache_key not in st.session_state:
                st.session_state[cache_key] = format_message_with_references(clean_content)
            formatted_content = st.session_state[cache_key]
            
            st.markdown(f"""
            <div class="message-bubble assistant-message">
                <div class="message-sender">{agent_config['icon']} {agent_config['name']}</div>
                {formatted_content}
                <div class="message-time">{message_time}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show downloadable files and image ONLY for the latest assistant message
            is_last_assistant = (i == len(filtered_messages) - 1)
            if is_last_assistant:
                client = st.session_state.ai_clients.get(azure_agent_id)
                if client:
                    display_downloadable_files(clean_content, client)
                if message.get("image_path"):
                    try:
                        import os
                        from PIL import Image
                        if os.path.exists(message["image_path"]):
                            img = Image.open(message["image_path"])
                            st.image(img, caption="Generated by Code Interpreter")
                    except Exception as img_error:
                        st.warning(f"Could not display image: {img_error}")
            

    
    st.markdown('</div>', unsafe_allow_html=True)

    # (Old bottom controls removed; now at top)

    # Placeholder for immediate (ephemeral) user + loading messages ABOVE input
    new_message_placeholder = st.empty()

    # Chat input - stays at the very bottom visually
    user_input = st.chat_input(f"Ask {agent_config['name']}...", key=f"chat_{azure_agent_id}")

    if user_input:
        # Ensure message history list exists
        if azure_agent_id not in st.session_state.messages:
            st.session_state.messages[azure_agent_id] = []

        clean_user_input = clean_message_content(user_input)
        current_thread_id = st.session_state.thread_ids.get(azure_agent_id)
        current_conversation_id = st.session_state.get('conversation_ids', {}).get(azure_agent_id)
        
        # Generate conversation ID if not exists (for first message in conversation)
        if not current_conversation_id:
            import uuid
            current_conversation_id = str(uuid.uuid4())
            if 'conversation_ids' not in st.session_state:
                st.session_state.conversation_ids = {}
            st.session_state.conversation_ids[azure_agent_id] = current_conversation_id
        
        # Ensure we have a valid thread_id before proceeding
        if not current_thread_id:
            st.error("❌ Thread ID bulunamadı. Lütfen sayfayı yenileyin.")
            st.stop()
            
        # Append user message to persistent history immediately, tagged with current thread and conversation
        st.session_state.messages[azure_agent_id].append({
            "role": "user",
            "content": clean_user_input,
            "thread_id": current_thread_id,
            "conversation_id": current_conversation_id,
            "timestamp": datetime.now().isoformat()  # Add timestamp for better tracking
        })

        # Show user message + loading bubble in placeholder (keeps input at bottom)
        with new_message_placeholder.container():
            message_time = datetime.now().strftime("%H:%M")
            st.markdown(f"""
            <div class="message-bubble user-message">
                <div class="message-sender">👤 Sen</div>
                {clean_user_input}
                <div class="message-time">{message_time}</div>
            </div>
            <div class="message-bubble assistant-message">
                <div class="message-sender">{agent_config['icon']} {agent_config['name']}</div>
                <div class="loading-text">
                    <span class="loading-spinner"></span>
                    Yanıt hazırlanıyor...
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Get assistant response (blocking)
        assistant_message = process_ai_response(user_input, azure_agent_id, agent_config)

        # Replace loading with final assistant response (also already added to history inside process_ai_response)
        if assistant_message:
            with new_message_placeholder.container():
                response_time = datetime.now().strftime("%H:%M")
                formatted_content = format_message_with_references(assistant_message['content'])
                st.markdown(f"""
                <div class="message-bubble user-message">
                    <div class="message-sender">👤 Sen</div>
                    {clean_user_input}
                    <div class="message-time">{message_time}</div>
                </div>
                <div class="message-bubble assistant-message">
                    <div class="message-sender">{agent_config['icon']} {agent_config['name']}</div>
                    {formatted_content}
                    <div class="message-time">{response_time}</div>
                </div>
                """, unsafe_allow_html=True)

                # Optional image (avoid duplicate rendering across prompts)
                if assistant_message.get('image_path'):
                    # Initialize per-agent displayed images tracker
                    if 'displayed_images_by_agent' not in st.session_state:
                        st.session_state.displayed_images_by_agent = {}
                    if azure_agent_id not in st.session_state.displayed_images_by_agent:
                        st.session_state.displayed_images_by_agent[azure_agent_id] = set()
                    img_path = assistant_message['image_path']
                    try:
                        import os
                        from PIL import Image
                        if os.path.exists(img_path):
                            # Only display if not already shown for this agent in this thread
                            if img_path not in st.session_state.displayed_images_by_agent[azure_agent_id]:
                                img = Image.open(img_path)
                                st.image(img, caption="Generated by Code Interpreter")
                                st.session_state.displayed_images_by_agent[azure_agent_id].add(img_path)
                    except Exception:
                        pass

                # Downloadable file links (use assistant content)
                client_check = st.session_state.ai_clients.get(azure_agent_id)
                if client_check and assistant_message.get('content'):
                    display_downloadable_files(assistant_message['content'], client_check)

        # Final rerun so that both messages render in the persistent history ABOVE the input cleanly
        st.rerun()


def process_ai_response(user_input: str, agent_id: str, agent_config: Dict) -> Dict:
    """Process user input and get AI response, returning the assistant message"""
    try:
        client = st.session_state.ai_clients[agent_id]
        thread_id = st.session_state.thread_ids[agent_id]

        # Check client and agent
        if client is None:
            return {"role": "assistant", "content": "Azure AI Foundry client not available. Please ensure Azure AI Project connection is working."}
        if not hasattr(client, 'agent') or client.agent is None:
            return {"role": "assistant", "content": "Azure AI Foundry agent not loaded. Please check your agent configuration and connection."}

        agent_type = agent_config.get('agent_type', 'Data Agent')

        # Build inputs and call appropriate client method
        if agent_type == 'Data Analyzer':
            enhanced_input = user_input
            data_container = agent_config.get('data_container', '')
            data_file = agent_config.get('data_file', '')
            if data_container and data_file:
                enhanced_input = f"""Şu dosyayı bulup analiz et: {data_file}

Dosya bilgileri:
- Dosya adı: {data_file}  
- Container: {data_container}
- Dosya türü: Excel (.xlsx) satış verisi

ADIMLAR:
1. Önce import os; os.listdir('.') ile mevcut dosyaları listele
2. Eğer dosya listede varsa pandas.read_excel() ile oku
3. Dosya yoksa bana bildir

Kullanıcının sorusu: {user_input}"""
            else:
                enhanced_input = f"""Code interpreter modunda çalışıyorum.

Kullanıcının sorusu: {user_input}

Eğer veri analizi gerekiyorsa, önce mevcut dosyaları kontrol edelim:
import os
print("Mevcut dosyalar:", os.listdir('.'))"""

            if any(word in user_input.lower() for word in ["tl", "lira", "para", "tutar", "satış", "gelir", "million", "milyon"]):
                enhanced_input += "\n\nÖNEMLİ: Grafik oluştururken, y ekseni etiketlerini doğru birim ile belirt. Eğer değerler milyon TL civarındaysa (2.5, 2.7 gibi), y ekseni etiketi 'Milyon TL' olmalı. Eğer değerler bin TL civarındaysa (2500, 2700 gibi), 'Bin TL' olmalı. Değerlerin büyüklüğüne göre doğru birimi seç."

            response_text, image_path, code_snippet = client.send_message_with_code_interpreter(thread_id, enhanced_input)

            # Persist image if exists
            if image_path and os.path.exists(image_path):
                try:
                    import shutil, time
                    persist_dir = os.path.join(os.path.dirname(__file__), 'generated_charts')
                    os.makedirs(persist_dir, exist_ok=True)
                    stable_name = f"{agent_id}_{int(time.time()*1000)}.png"
                    stable_path = os.path.join(persist_dir, stable_name)
                    shutil.copyfile(image_path, stable_path)
                    image_path = stable_path
                except Exception:
                    pass

            clean_response_text = clean_message_content(response_text)
            validated_response_text = validate_chart_currency_labels(clean_response_text, image_path)
            assistant_message = {"role": "assistant", "content": validated_response_text, "image_path": image_path, "code_snippet": code_snippet}
        else:
            # Data Agent
            code_keywords = ["chart", "graph", "plot", "visualize", "grafik", "tablo", "analiz", "calculate", "hesapla"]
            is_code_request = any(keyword.lower() in user_input.lower() for keyword in code_keywords)

            if is_code_request and hasattr(client, 'send_message_with_code_interpreter'):
                enhanced_input = user_input
                if any(word in user_input.lower() for word in ["tl", "lira", "para", "tutar", "satış", "gelir"]):
                    enhanced_input += "\n\nÖNEMLİ: Grafik oluştururken, y ekseni etiketlerini doğru birim ile belirt. Eğer değerler milyon TL civarındaysa (2.5, 2.7 gibi), y ekseni etiketi 'Milyon TL' olmalı. Eğer değerler bin TL civarındaysa (2500, 2700 gibi), 'Bin TL' olmalı. Değerlerin büyüklüğüne göre doğru birimi seç."

                if agent_config.get('send_user_info'):
                    current_username = st.session_state.get('current_user')
                    full_name = None
                    if current_username and st.session_state.get('user_manager'):
                        try:
                            udata = st.session_state.user_manager.get_user(current_username)
                            if udata:
                                name_part = udata.get('name') or udata.get('first_name') or ''
                                surname_part = udata.get('surname') or udata.get('last_name') or ''
                                full_name = (name_part + ' ' + surname_part).strip()
                        except Exception:
                            pass
                    if current_username:
                        info_block = "\n\n[Kullanıcı Bilgileri]\n" + (f"Ad Soyad: {full_name}\n" if full_name else "") + f"Email: {current_username}"
                        enhanced_input = enhanced_input + info_block

                response_text, image_path, code_snippet = client.send_message_with_code_interpreter(thread_id, enhanced_input)

                if image_path and os.path.exists(image_path):
                    try:
                        import shutil, time
                        persist_dir = os.path.join(os.path.dirname(__file__), 'generated_charts')
                        os.makedirs(persist_dir, exist_ok=True)
                        stable_name = f"{agent_id}_{int(time.time()*1000)}.png"
                        stable_path = os.path.join(persist_dir, stable_name)
                        shutil.copyfile(image_path, stable_path)
                        image_path = stable_path
                    except Exception:
                        pass

                clean_response_text = clean_message_content(response_text)
                validated_response_text = validate_chart_currency_labels(clean_response_text, image_path)
                assistant_message = {"role": "assistant", "content": validated_response_text, "image_path": image_path, "code_snippet": code_snippet}
            else:
                final_input = user_input
                if agent_config.get('send_user_info'):
                    current_username = st.session_state.get('current_user')
                    full_name = None
                    if current_username and st.session_state.get('user_manager'):
                        try:
                            udata = st.session_state.user_manager.get_user(current_username)
                            if udata:
                                name_part = udata.get('name') or udata.get('first_name') or ''
                                surname_part = udata.get('surname') or udata.get('last_name') or ''
                                full_name = (name_part + ' ' + surname_part).strip()
                        except Exception:
                            pass
                    if current_username:
                        info_block = "\n\n[Kullanıcı Bilgileri]\n" + (f"Ad Soyad: {full_name}\n" if full_name else "") + f"Email: {current_username}"
                        final_input = user_input + info_block

                response_text = client.send_message_and_get_response(thread_id, final_input)

                clean_response_text = clean_message_content(response_text)
                assistant_message = {"role": "assistant", "content": clean_response_text}

        # Check for duplicate response before saving
        response_content = assistant_message.get('content', '')
        if is_duplicate_response(response_content, agent_id, user_input):
            # Generate a new response instead of using the duplicate
            st.warning("🔄 Duplicate response detected, regenerating...")
            # Force a slight delay and retry with modified input
            import time
            time.sleep(1)
            modified_input = f"{user_input} [Lütfen farklı bir perspektiften yaklaş]"
            return process_ai_response(modified_input, agent_id, agent_config)
        
        # Register this response to prevent future duplicates
        register_response(response_content, agent_id, user_input)
        
        # Append assistant message to persistent history
        if agent_id not in st.session_state.messages:
            st.session_state.messages[agent_id] = []
            
        # Tag assistant message with the thread id and conversation id for complete isolation
        current_thread_id = st.session_state.thread_ids.get(agent_id)
        current_conversation_id = st.session_state.get('conversation_ids', {}).get(agent_id)
        
        if current_thread_id:
            assistant_message["thread_id"] = current_thread_id
            if current_conversation_id:
                assistant_message["conversation_id"] = current_conversation_id
            assistant_message["timestamp"] = datetime.now().isoformat()
            st.session_state.messages[agent_id].append(assistant_message)
        else:
            # If no thread_id, don't save the message (this prevents orphaned messages)
            st.warning("⚠️ Thread ID eksik - mesaj kaydedilmedi")
        return assistant_message
        
    except Exception as e:
        error_msg = f"Error getting response from Azure AI Foundry: {str(e)}"
        return {"role": "assistant", "content": clean_message_content(error_msg)}


def show_document_management(agent_config: Dict):
    """Display document management interface"""
    
    agent_id = agent_config['id']
    
    # Check permissions first
    if st.session_state.user_role == "admin":
        can_upload = True
        can_delete = True
        can_download = True
    elif not st.session_state.user_manager or not st.session_state.current_user:
        can_upload = False
        can_delete = False
        can_download = False
    else:
        can_upload = st.session_state.user_manager.has_permission(
            st.session_state.current_user, agent_id, "document_upload")
        can_delete = st.session_state.user_manager.has_permission(
            st.session_state.current_user, agent_id, "document_delete")
        can_download = st.session_state.user_manager.has_permission(
            st.session_state.current_user, agent_id, "document_download")
    
    # Show permission status
    if not can_upload and not can_delete and not can_download:
        st.error("🚫 Document Access Denied: You don't have any document management permissions for this agent")
        st.warning("⚠️ Please contact your administrator to request document upload, download, or delete permissions.")
        return
    
    # Document upload section
    if can_upload:
        st.subheader("📤 Upload Documents")
        
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx'],
            accept_multiple_files=True,
            key=f"upload_{agent_id}"
        )
        
        if uploaded_files:
            if st.button("🚀 Upload Files", key=f"upload_btn_{agent_id}"):
                try:
                    # Initialize client if needed
                    if agent_id not in st.session_state.ai_clients:
                        from azure_utils import EnhancedAzureAIAgentClient, AzureConfig
                        config = AzureConfig()
                        client = EnhancedAzureAIAgentClient(
                            agent_config['connection_string'],
                            agent_config['agent_id'],
                            config,
                            agent_config.get('container_name', '')  # Pass container name
                        )
                        st.session_state.ai_clients[agent_id] = client
                    
                    client = st.session_state.ai_clients[agent_id]
                    container_name = agent_config['container_name']
                    
                    success_count = 0
                    error_details = []
                    success_details = []
                    
                    with st.spinner("Uploading documents to blob storage..."):
                        for uploaded_file in uploaded_files:
                            try:
                                file_content = uploaded_file.read()
                                
                                # Get index name from agent config
                                index_name = agent_config.get('search_index')
                                
                                # Upload document with indexing
                                result = client.upload_and_index_document(
                                    container_name,
                                    uploaded_file.name,
                                    file_content,
                                    uploaded_file.type or "application/octet-stream",
                                    index_name
                                )
                                
                                if result['success']:
                                    success_count += 1
                                    success_details.append(f"📁 {uploaded_file.name}: ✅ Uploaded to blob storage")
                                    # Show indexing status
                                    if result.get('indexed'):
                                        success_details.append(f"🔍 {uploaded_file.name}: ✅ Indexing triggered")
                                    elif index_name:
                                        success_details.append(f"🔍 {uploaded_file.name}: ⚠️ Indexing failed - {result.get('index_message', 'Unknown error')}")
                                else:
                                    error_details.append(f"❌ {uploaded_file.name}: {result.get('message', 'Upload failed')}")
                                    
                            except Exception as file_error:
                                error_details.append(f"💥 {uploaded_file.name}: {str(file_error)}")
                    
                    # Show detailed results with indexing status
                    if success_count == len(uploaded_files):
                        st.success(f"✅ Successfully uploaded {success_count}/{len(uploaded_files)} files to blob storage!")
                        # Check if any files had indexing
                        any_indexed = any('✅ Indexing triggered' in detail for detail in success_details)
                        if any_indexed:
                            st.info("🔍 Indexing has been triggered for search functionality")
                        if success_details:
                            with st.expander("📋 Upload Details"):
                                for detail in success_details:
                                    st.write(detail)
                    else:
                        st.error(f"❌ Only {success_count}/{len(uploaded_files)} files uploaded successfully")
                        if error_details:
                            with st.expander("📋 Error Details"):
                                for detail in error_details:
                                    st.write(detail)
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Upload operation failed: {str(e)}")
                    st.info("💡 If you're seeing a 400 error, this might be due to:")
                    st.write("• File size too large (limit: 200MB per file)")
                    st.write("• Unsupported file format")
                    st.write("• Azure service configuration issues")
                    st.write("• Network connectivity problems")
                    
                    with st.expander("🔧 Troubleshooting"):
                        st.write("1. Check if the file is a supported format (PDF, DOC, DOCX, TXT, XLS, XLSX, PPT, PPTX)")
                        st.write("2. Ensure file size is under 200MB")
                        st.write("3. Try uploading one file at a time")
                        st.write("4. Contact administrator if the problem persists")
    else:
        st.info("ℹ️ Document upload permission not available for this agent")
    
    st.markdown("---")
    
    # Document list section - check permission to view documents
    if st.session_state.user_role == "admin":
        can_view_docs = True
    elif can_upload or can_delete or can_download:
        # If user can upload/delete/download, they can view
        can_view_docs = True
    elif not st.session_state.user_manager or not st.session_state.current_user:
        can_view_docs = False
    else:
        # Basic access allows viewing
        can_view_docs = st.session_state.user_manager.has_permission(
            st.session_state.current_user, agent_id, "access")
    
    if not can_view_docs:
        st.warning("⚠️ You don't have permission to view documents for this agent")
        return
    
    st.subheader("📁 Document Library")
    
    try:
        # Initialize client if needed
        if agent_id not in st.session_state.ai_clients:
            from azure_utils import EnhancedAzureAIAgentClient, AzureConfig
            config = AzureConfig()
            client = EnhancedAzureAIAgentClient(
                agent_config['connection_string'],
                agent_config['agent_id'],
                config,
                agent_config.get('container_name', '')  # Pass container name
            )
            st.session_state.ai_clients[agent_id] = client
        
        client = st.session_state.ai_clients[agent_id]
        container_name = agent_config['container_name']
        
        documents = client.list_documents(container_name)
        
        if documents:
            # Add document search and bulk operations with right-aligned delete button
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                # Search functionality - compact input field
                search_query = st.text_input("🔍 Ara:", 
                                           placeholder="Doküman adı...",
                                           key=f"doc_search_{agent_id}")
            
            with col2:
                # Empty column for spacing
                st.markdown("&nbsp;", unsafe_allow_html=True)
            
            with col3:
                # Add spacing for button alignment and right-align delete button
                st.markdown("&nbsp;", unsafe_allow_html=True)
                # Delete all documents button with confirmation - right aligned
                if can_delete:
                    if st.button("🗑️ Tüm Dökümanları Sil", 
                               key=f"delete_all_{agent_id}", 
                               type="secondary"):
                        st.session_state[f"confirm_delete_all_{agent_id}"] = True
                        st.rerun()
            
            # Confirmation dialog (outside columns)
            if can_delete and st.session_state.get(f"confirm_delete_all_{agent_id}", False):
                st.warning("⚠️ **UYARI: Tüm dökümanlar silinecektir, emin misiniz?**")
                col_yes, col_no = st.columns(2)
                
                with col_yes:
                    if st.button("✅ Evet, Tümünü Sil", key=f"confirm_yes_{agent_id}", type="primary"):
                        try:
                            index_name = agent_config.get('search_index')
                            if not index_name:
                                st.error("❌ Bu ajan için search index yapılandırılmamış.")
                            else:
                                deleted_count = 0
                                failed_count = 0
                                
                                # Delete each document
                                for doc in documents:
                                    if client.delete_document(container_name, doc['name'], index_name):
                                        deleted_count += 1
                                    else:
                                        failed_count += 1
                                
                                if deleted_count > 0:
                                    st.success(f"✅ {deleted_count} doküman başarıyla silindi!")
                                if failed_count > 0:
                                    st.error(f"❌ {failed_count} doküman silinemedi.")
                                
                                st.session_state[f"confirm_delete_all_{agent_id}"] = False
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Toplu silme hatası: {str(e)}")
                            st.session_state[f"confirm_delete_all_{agent_id}"] = False
                
                with col_no:
                    if st.button("❌ Hayır, İptal Et", key=f"confirm_no_{agent_id}"):
                        st.session_state[f"confirm_delete_all_{agent_id}"] = False
                        st.rerun()
            
            # Remove predefined sample/demo documents
            SAMPLE_DOC_NAMES = {"sample_report.pdf", "data_analysis.xlsx", "meeting_notes.docx"}
            documents = [d for d in documents if d.get('name','').lower() not in SAMPLE_DOC_NAMES]

            # Filter documents based on search query
            filtered_documents = documents
            if search_query:
                filtered_documents = [
                    doc for doc in documents 
                    if search_query.lower() in doc['name'].lower()
                ]
                st.info(f"🔍 {len(filtered_documents)} doküman bulundu (toplam {len(documents)} doküman)")
            
            # Add size_mb to filtered documents
            for doc in filtered_documents:
                doc['size_mb'] = (doc['size'] / 1024 / 1024) if doc['size'] else 0
            
            # Display filtered documents
            if filtered_documents:
                for idx, doc in enumerate(filtered_documents):
                    with st.expander(f"📄 {doc['name']} ({doc['size_mb']:.2f} MB)"):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.write(f"**Size:** {doc['size_mb']:.2f} MB")
                            st.write(f"**Modified:** {doc['last_modified']}")
                            st.write(f"**Type:** {doc['content_type']}")
                        
                        with col2:
                            if can_download:
                                if st.button("📥 Download", key=f"download_{agent_id}_{idx}"):
                                    try:
                                        # Download document from blob storage
                                        download_result = client.download_document(container_name, doc['name'])
                                        if download_result['success']:
                                            # Provide download button
                                            st.download_button(
                                                label=f"💾 Save {doc['name']}",
                                                data=download_result['content'],
                                                file_name=doc['name'],
                                                mime=doc.get('content_type', 'application/octet-stream'),
                                                key=f"save_{agent_id}_{idx}"
                                            )
                                            st.success(f"✅ {doc['name']} ready for download!")
                                        else:
                                            st.error(f"❌ Failed to download {doc['name']}: {download_result.get('message', 'Unknown error')}")
                                    except Exception as e:
                                        st.error(f"❌ Download error: {str(e)}")
                            else:
                                st.write("🔒 No download permission")
                        
                        with col3:
                            if can_delete:
                                if st.button("🗑️ Delete", key=f"delete_{agent_id}_{idx}", type="secondary"):
                                    # Get index name from agent config - strict mode, no fallback
                                    index_name = agent_config.get('search_index')
                                    if not index_name:
                                        st.error(f"❌ No search index configured for agent '{agent_id}'. Please configure 'search_index' in agent settings.")
                                    else:
                                        if client.delete_document(container_name, doc['name'], index_name):
                                            st.success(f"✅ Deleted {doc['name']}")
                                            st.info("🔄 Reindexing triggered automatically")
                                            st.rerun()
                                        else:
                                            st.error(f"❌ Failed to delete {doc['name']} from index '{index_name}'")
                            else:
                                st.write("🔒 No delete permission")
            else:
                if search_query:
                    st.info(f"🔍 '{search_query}' araması için sonuç bulunamadı")
                else:
                    st.info("📭 No documents found")
        else:
            st.info("📭 No documents found in this agent's library")
    
    except Exception as e:
        st.error(f"❌ Error loading documents: {str(e)}")

def show_agent_settings(agent_config: Dict):
    """Display agent settings and configuration"""
    
    st.subheader("⚙️ Agent Configuration")
    
    # Display current settings
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Connection Details:**")
        st.code(f"Agent ID: {agent_config['agent_id']}")
        st.code(f"Container: {agent_config['container_name']}")
    
    with col2:
        st.markdown("**Agent Properties:**")
        st.write(f"**Name:** {agent_config['name']}")
        st.write(f"**Icon:** {agent_config['icon']}")
        st.write(f"**Color:** {agent_config['color']}")
        st.write(f"**Categories:** {', '.join(agent_config['categories'])}")
    
    # Connection status
    agent_id = agent_config['id']
    if agent_id in st.session_state.connection_status:
        status = st.session_state.connection_status[agent_id]
        if status:
            st.success("🟢 Agent Connected")
        else:
            st.error("🔴 Agent Disconnected")
    else:
        st.info("⚪ Connection Not Tested")
    
    # Test connection button
    if st.button("🔌 Test Connection", key=f"test_{agent_id}"):
        try:
            from azure_utils import EnhancedAzureAIAgentClient, AzureConfig
            config = AzureConfig()
            client = EnhancedAzureAIAgentClient(
                agent_config['connection_string'],
                agent_config['agent_id'],
                config,
                agent_config.get('container_name', '')  # Pass container name
            )
            st.success("✅ Connection test successful!")
            st.session_state.connection_status[agent_id] = True
        except Exception as e:
            st.error(f"❌ Connection test failed: {str(e)}")
            st.session_state.connection_status[agent_id] = False

def show_settings():
    """Display comprehensive settings interface for admin users with blob storage integration"""
    
    if st.session_state.user_role != "admin":
        st.error("⚠️ Admin access required")
        return
    
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown('<h1 class="main-header">⚙️ Settings (Blob Storage)</h1>', unsafe_allow_html=True)
    with col2:
        if st.button("🏠 Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    # Settings tabs
    tab1, tab2, tab3 = st.tabs(["👥 User Management", "🤖 Agent Configuration", "🔧 System Settings"])
    
    with tab1:
        show_blob_user_management_tab()
    
    with tab2:
        show_blob_agent_configuration_tab()
    
    with tab3:
        show_system_settings_tab()

def show_blob_user_management_tab():
    """Enhanced user management tab with blob storage integration"""
    st.subheader("📋 User Management (Blob Storage)")
    
    # Check if user_manager is available
    if st.session_state.user_manager is None:
        st.error("❌ User management is currently disabled due to Azure connection issues.")
        st.info("💡 User management requires Azure Blob Storage connection. Please check your Azure configuration.")
        return
    
    # Get current users from blob storage
    try:
        users = st.session_state.user_manager.get_all_users()
        
        # Ensure users is a dictionary
        if not isinstance(users, dict):
            st.error(f"❌ Invalid user data format. Expected dictionary, got {type(users)}")
            users = {}
        # Exclude activity log users from the list
        else:
            users = {u: d for u, d in users.items() if not str(u).startswith("activiy_admin")}
    except Exception as e:
        st.error(f"❌ Error loading users: {e}")
        users = {}
    
    # Get agents from blob storage as well
    from azure_utils import AzureConfig, BlobStorageAgentManager
    try:
        # Initialize without any extra parameters
        blob_agent_manager = BlobStorageAgentManager(AzureConfig())
        agents = blob_agent_manager.get_all_agents()
    except Exception as e:
        st.error(f"Error loading agents from blob storage: {e}")
        agents = {}
    
    # Add new user section
    with st.expander("➕ Add New User"):
        # Show success message from previous add (after rerun)
        if st.session_state.get("user_add_success"):
            added_username = st.session_state.get("user_add_success_username", "")
            if added_username:
                st.success(f"✅ User '{added_username}' added successfully and saved to blob storage!")
            else:
                st.success("✅ User added successfully and saved to blob storage!")
            # Clear flags so it only shows once
            st.session_state.pop("user_add_success", None)
            st.session_state.pop("user_add_success_username", None)

        with st.form("add_user_form_settings"):
            new_username = st.text_input("Username", placeholder="Enter username")
            new_role = st.selectbox("Role", ["standard", "admin"])
            
            st.write("**Agent Permissions:**")
            new_permissions = {}
            
            for agent_id, agent_config in agents.items():
                st.write(f"**{agent_config['name']} ({agent_id})**")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    access = st.checkbox(f"Access", key=f"blob_new_access_{agent_id}")
                with col2:
                    chat = st.checkbox(f"Chat", key=f"blob_new_chat_{agent_id}")
                with col3:
                    upload = st.checkbox(f"Upload", key=f"blob_new_upload_{agent_id}")
                with col4:
                    download = st.checkbox(f"Download", key=f"blob_new_download_{agent_id}")
                with col5:
                    delete = st.checkbox(f"Delete", key=f"blob_new_delete_{agent_id}")
                
                new_permissions[agent_id] = {
                    'access': access,
                    'chat': chat,
                    'document_upload': upload,
                    'document_download': download,
                    'document_delete': delete
                }
            
            if st.form_submit_button("➕ Add User", type="primary"):
                if new_username and new_username not in users:
                    # No password needed - users will authenticate with Azure AD
                    if st.session_state.user_manager.add_user(new_username, new_role, None, new_permissions):
                        # Store success state then rerun to show message cleanly
                        st.session_state["user_add_success"] = True
                        st.session_state["user_add_success_username"] = new_username
                        st.rerun()
                    else:
                        st.error("❌ Failed to add user to blob storage")
                elif new_username in users:
                    st.error("❌ Username already exists")
                else:
                    st.error("❌ Please enter a username")
    
    # Display current users
    st.markdown("---")
    
    if users:
        for username, user_data in users.items():
            # Ensure user_data is a dictionary
            if not isinstance(user_data, dict):
                st.error(f"❌ Invalid user data for {username}: {type(user_data)}")
                continue
                
            with st.expander(f"👤 {username} ({user_data.get('role', 'Unknown')}) - Created: {user_data.get('created_at', 'Unknown')[:10]}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Role:** {user_data.get('role', 'Unknown')}")
                    st.write(f"**Created:** {user_data.get('created_at', 'Unknown')}")
                    if user_data.get('updated_at'):
                        st.write(f"**Last Updated:** {user_data.get('updated_at')}")
            
            with col2:
                # Blob storage operations
                if st.button(f"🔄 Refresh", key=f"refresh_{username}"):
                    # Force reload from blob storage
                    st.session_state.user_manager = st.session_state.user_manager.__class__()
                    st.rerun()
            
            if user_data.get('role') != 'admin':
                st.write("**Agent Permissions:**")
                
                # Permission matrix
                permission_data = []
                user_permissions = user_data.get('permissions', [])
                
                for agent_id, agent_config in agents.items():
                    # Handle both new list format and old dictionary format
                    if isinstance(user_permissions, list):
                        # New list format
                        has_access = f"{agent_id}:access" in user_permissions or "access" in user_permissions
                        has_chat = f"{agent_id}:chat" in user_permissions or "chat" in user_permissions
                        has_upload = f"{agent_id}:document_upload" in user_permissions or "document_upload" in user_permissions
                        has_download = f"{agent_id}:document_download" in user_permissions or "document_download" in user_permissions
                        has_delete = f"{agent_id}:document_delete" in user_permissions or "document_delete" in user_permissions
                    else:
                        # Old dictionary format (fallback)
                        user_perms = user_permissions.get(agent_id, {}) if isinstance(user_permissions, dict) else {}
                        has_access = user_perms.get('access', False)
                        has_chat = user_perms.get('chat', False)
                        has_upload = user_perms.get('document_upload', False)
                        has_download = user_perms.get('document_download', False)
                        has_delete = user_perms.get('document_delete', False)
                    
                    permission_data.append({
                        'Agent': agent_config['name'],
                        'Agent ID': agent_id,
                        'Access': '✅' if has_access else '❌',
                        'Chat': '✅' if has_chat else '❌',
                        'Upload': '✅' if has_upload else '❌',
                        'Download': '✅' if has_download else '❌',
                        'Delete': '✅' if has_delete else '❌'
                    })
                
                if permission_data:
                    df_perms = pd.DataFrame(permission_data)
                    st.dataframe(df_perms)
                else:
                    st.info("No specific permissions set")
                
                # Edit permissions button
                if st.button(f"✏️ Edit Permissions", key=f"edit_{username}"):
                    st.session_state[f"editing_{username}"] = True
                    st.rerun()
                
                # Edit permissions form
                if st.session_state.get(f"editing_{username}", False):
                    st.write("**Edit Permissions (Will save to blob storage):**")
                    with st.form(f"edit_perms_{username}"):
                        updated_permissions = []  # Use list format for new system
                        
                        for agent_id, agent_config in agents.items():
                            st.write(f"**{agent_config['name']} ({agent_id})**")
                            col1, col2, col3, col4, col5 = st.columns(5)
                            
                            # Get current permissions in both formats
                            user_permissions = user_data.get('permissions', [])
                            if isinstance(user_permissions, list):
                                # New list format
                                current_access = f"{agent_id}:access" in user_permissions or "access" in user_permissions
                                current_chat = f"{agent_id}:chat" in user_permissions or "chat" in user_permissions
                                current_upload = f"{agent_id}:document_upload" in user_permissions or "document_upload" in user_permissions
                                current_download = f"{agent_id}:document_download" in user_permissions or "document_download" in user_permissions
                                current_delete = f"{agent_id}:document_delete" in user_permissions or "document_delete" in user_permissions
                            else:
                                # Old dictionary format (fallback)
                                current_perms = user_permissions.get(agent_id, {}) if isinstance(user_permissions, dict) else {}
                                current_access = current_perms.get('access', False)
                                current_chat = current_perms.get('chat', False)
                                current_upload = current_perms.get('document_upload', False)
                                current_download = current_perms.get('document_download', False)
                                current_delete = current_perms.get('document_delete', False)
                            
                            with col1:
                                access = st.checkbox("Access", 
                                                   value=current_access,
                                                   key=f"edit_access_{username}_{agent_id}")
                            with col2:
                                chat = st.checkbox("Chat", 
                                                 value=current_chat,
                                                 key=f"edit_chat_{username}_{agent_id}")
                            with col3:
                                upload = st.checkbox("Upload", 
                                                    value=current_upload,
                                                    key=f"edit_upload_{username}_{agent_id}")
                            with col4:
                                download = st.checkbox("Download", 
                                                      value=current_download,
                                                      key=f"edit_download_{username}_{agent_id}")
                            with col5:
                                delete = st.checkbox("Delete", 
                                                    value=current_delete,
                                                    key=f"edit_delete_{username}_{agent_id}")
                            
                            # Build permission list in new format
                            if access:
                                updated_permissions.append(f"{agent_id}:access")
                            if chat:
                                updated_permissions.append(f"{agent_id}:chat")
                            if upload:
                                updated_permissions.append(f"{agent_id}:document_upload")
                            if download:
                                updated_permissions.append(f"{agent_id}:document_download")
                            if delete:
                                updated_permissions.append(f"{agent_id}:document_delete")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Save to Blob Storage", type="primary"):
                                if st.session_state.user_manager.update_user_permissions(username, updated_permissions):
                                    st.session_state[f"editing_{username}"] = False
                                    st.success("✅ Permissions updated and saved to blob storage!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to save permissions to blob storage")
                        with col2:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state[f"editing_{username}"] = False
                                st.rerun()
            else:
                st.success("👑 Full admin access to all agents and features")
            
            # Delete user button (except for admin)
            if username != "admin":
                if st.button(f"🗑️ Delete User (from Blob)", key=f"delete_{username}", type="secondary"):
                    if st.session_state.user_manager.delete_user(username):
                        st.success(f"🗑️ User {username} deleted from blob storage!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete user from blob storage")

def show_blob_agent_configuration_tab():
    """Enhanced agent configuration tab with blob storage integration"""
    st.subheader("🤖 Agent Configuration (Blob Storage)")
    
    # Check if Azure connection is available
    try:
        # Get current agents from blob storage using AgentManager
        from azure_utils import AzureConfig, BlobStorageAgentManager
        # Initialize without any extra parameters
        blob_agent_manager = BlobStorageAgentManager(AzureConfig())
        agents = blob_agent_manager.get_all_agents()
        
        # If no agents from blob storage, try backup configuration as fallback
        if not agents:
            backup_path = "config_backup/agent_configs.json"
            if os.path.exists(backup_path):
                import json
                with open(backup_path, 'r', encoding='utf-8') as f:
                    all_agents = json.load(f)
                # Convert backup format to expected format with all required fields
                agents = {}
                for agent_id, config in all_agents.items():
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
                        'enabled': config.get('enabled', True),
                        'status': 'active' if config.get('enabled', True) else 'inactive',
                        'created_at': config.get('created_at', '2025-01-01T00:00:00Z'),
                        'agent_type': config.get('agent_type', 'Data Agent'),
                        'data_container': config.get('data_container', ''),
                        'data_file': config.get('data_file', '')
                    }
                st.info(f"📂 Loaded {len(agents)} agents from backup configuration (blob storage not available)")
        
    except Exception as e:
        st.error(f"❌ Azure Blob Storage connection failed: {e}")
        st.warning("⚠️ Agent configuration requires Azure Blob Storage connection.")
        st.info("💡 Using session state agents as fallback...")
        
        # Use session state agents as fallback
        agents = st.session_state.get("agents", {})
        
        if not agents:
            # Try backup configuration as final fallback
            backup_path = "config_backup/agent_configs.json"
            if os.path.exists(backup_path):
                try:
                    import json
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        all_agents = json.load(f)
                    # Convert backup format to expected format with all required fields
                    agents = {}
                    for agent_id, config in all_agents.items():
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
                            'enabled': config.get('enabled', True),
                            'status': 'active' if config.get('enabled', True) else 'inactive',
                            'created_at': config.get('created_at', '2025-01-01T00:00:00Z'),
                            'agent_type': config.get('agent_type', 'Data Agent'),
                            'data_container': config.get('data_container', ''),
                            'data_file': config.get('data_file', '')
                        }
                    st.warning(f"⚠️ Fallback: Loaded {len(agents)} agents from backup configuration due to blob storage error")
                except Exception as backup_error:
                    st.error(f"Error loading backup configuration: {backup_error}")
                    agents = {}
    
    # Add new agent section
    with st.expander("➕ Add New Agent"):
        with st.form("add_agent_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_agent_id = st.text_input("Agent ID", placeholder="e.g., hr_agent")
                new_agent_name = st.text_input("Agent Name", placeholder="e.g., HR Assistant")
                
                # Agent Type Selection
                new_agent_type = st.selectbox(
                    "Agent Type",
                    options=["Data Agent", "Data Analyzer"],
                    index=0,
                    help="Data Agent: Standard document-based agent. Data Analyzer: Uses Azure AI code interpreter for data analysis."
                )
                
                # Icon selector - use radio for better form experience
                new_agent_icon = show_icon_selector(default_icon="🤖", key="add_agent", use_radio=True)
                
                new_agent_color = st.color_picker("Agent Color", "#FF6B6B")
            
            with col2:
                new_agent_description = st.text_area("Description", placeholder="Agent description")
                new_connection_string = st.text_input("Connection String", placeholder="Azure AI connection string")
                new_agent_ai_id = st.text_input("AI Agent ID", placeholder="Assistant ID")
                new_container_name = st.text_input("Container Name", placeholder="document-container")
                new_search_index = st.text_input("Search Index", placeholder="search-index-name", 
                                                help="Index name for search functionality")
            
            # Data Analyzer specific fields were removed to simplify configuration
            
            new_categories = st.text_input("Categories (comma-separated)", placeholder="category1, category2")
            
            if st.form_submit_button("➕ Add Agent", type="primary"):
                if new_agent_id and new_agent_name:
                    # Previously required Data Analyzer fields removed; no extra validation needed here
                    
                    agent_config = {
                        "id": new_agent_id,
                        "name": new_agent_name,
                        "icon": new_agent_icon or "🤖",
                        "description": new_agent_description,
                        "connection_string": new_connection_string,
                        "agent_id": new_agent_ai_id,
                        "container_name": new_container_name,
                        "search_index": new_search_index,
                        "color": new_agent_color,
                        "categories": [cat.strip() for cat in new_categories.split(",") if cat.strip()],
                        "agent_type": new_agent_type,
                        "data_container": new_data_container if new_agent_type == "Data Analyzer" else "",
                        "data_file": new_data_file if new_agent_type == "Data Analyzer" else ""
                    }
                    
                    if blob_agent_manager.add_agent(agent_config):
                        # Clear session state agents to force refresh from blob storage on next dashboard visit
                        if "agents" in st.session_state:
                            del st.session_state["agents"]
                        st.success(f"✅ Agent '{new_agent_name}' added successfully and saved to blob storage!")
                        st.success("🔄 Agent cache cleared - dashboard will show updated agents")
                        st.rerun()
                    else:
                        st.error("❌ Failed to add agent to blob storage")
                else:
                    st.error("❌ Please enter Agent ID and Name")
    
    # Display current agents
    st.markdown("---")
    
    for agent_id, agent_config in agents.items():
        status = agent_config.get('status', 'active')
        status_icon = "🟢" if status == 'active' else "🔴"

        # Keep expander state across reruns so Job Configuration panel stays visible
        expander_key = f"expand_agent_{agent_id}"
        is_expanded = st.session_state.get(expander_key, False)

        with st.expander(
            f"{status_icon} {agent_config.get('icon', '🤖')} {agent_config.get('name', agent_id)} - Created: {agent_config.get('created_at', 'Unknown')[:10]}",
            expanded=is_expanded,
        ):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**ID:** {agent_id}")
                st.write(f"**Name:** {agent_config.get('name', 'N/A')}")
                st.write(f"**Type:** {agent_config.get('agent_type', 'Data Agent')}")
                st.write(f"**Description:** {agent_config.get('description', 'N/A')}")
                st.write(f"**Status:** {status}")
            
            with col2:
                st.write(f"**Container:** {agent_config.get('container_name', 'N/A')}")
                st.write(f"**AI Agent ID:** {agent_config.get('agent_id', 'N/A')}")
                st.write(f"**Categories:** {', '.join(agent_config.get('categories', []))}")
                
                # Show data analyzer specific info
                if agent_config.get('agent_type') == 'Data Analyzer':
                    st.write(f"**Data Container:** {agent_config.get('data_container', 'N/A')}")
                    st.write(f"**Data File:** {agent_config.get('data_file', 'N/A')}")
                
                # Job Configuration Section for ALL agent types  
                # (Job Configuration button moved to inline with other buttons below)
                
                if st.session_state.get(f"show_jobs_{agent_id}", False):
                    st.markdown("#### 🔄 Job Management")
                    
                    # Get job manager and existing jobs
                    try:
                        from azure_utils import JobManager, AzureConfig
                        job_manager = JobManager(AzureConfig())
                        existing_jobs = job_manager.get_jobs_for_agent(agent_id)
                        
                        if existing_jobs:
                                st.write(f"**Existing Jobs ({len(existing_jobs)}):**")
                                for i, job in enumerate(existing_jobs):
                                    job_status = job.get('status', 'unknown')
                                    status_icon = "🟢" if job_status == 'completed' else "🔴" if job_status == 'failed' else "🟡"
                                    
                                    # Use container instead of expander to avoid nesting
                                    job_container = st.container()
                                    with job_container:
                                        st.markdown(f"**{status_icon} Job {i+1}: {job.get('id', 'Unknown')[:8]}... - Status: {job_status}**")
                                        
                                        col_job1, col_job2 = st.columns(2)
                                        with col_job1:
                                            schedule_type = job.get('schedule_type', 'Manual')
                                            schedule_display = schedule_type.title()
                                            
                                            if schedule_type == 'scheduled':
                                                period = job.get('schedule_period', 'daily')
                                                hour = job.get('schedule_hour', 0)
                                                minute = job.get('schedule_minute', 0)
                                                
                                                if period == 'daily':
                                                    schedule_display = f"Daily at {hour:02d}:{minute:02d}"
                                                elif period == 'weekly':
                                                    weekday = job.get('schedule_weekday', 'Monday')
                                                    schedule_display = f"Weekly ({weekday}) at {hour:02d}:{minute:02d}"
                                                elif period == 'monthly':
                                                    day = job.get('schedule_day', 1)
                                                    schedule_display = f"Monthly (Day {day}) at {hour:02d}:{minute:02d}"
                                                else:
                                                    schedule_display = f"Scheduled at {hour:02d}:{minute:02d}"
                                            
                                            st.write(f"• **Schedule:** {schedule_display}")
                                            st.write(f"• **Created:** {job.get('created_at', 'Unknown')[:16]}")
                                            st.write(f"• **Last Run:** {job.get('last_run', 'Never')[:16] if job.get('last_run') else 'Never'}")
                                        with col_job2:
                                            st.write(f"• **Data Container:** {job.get('data_container', 'N/A')}")
                                            st.write(f"• **Data Files:** {', '.join(job.get('data_files', [])[:2])}{'...' if len(job.get('data_files', [])) > 2 else ''}")
                                            if job.get('last_error'):
                                                st.error(f"Last Error: {job['last_error'][:100]}...")
                                        
                                        # Job actions
                                        col_action1, col_action2, col_action3 = st.columns(3)
                                        with col_action1:
                                            if st.button(f"▶️ Run", key=f"run_job_{i}_{agent_id}"):
                                                if job_manager.execute_job(job['id']):
                                                    st.success("✅ Job started!")
                                                    st.rerun()
                                                else:
                                                    st.error("❌ Failed to start job")
                                        with col_action2:
                                            if st.button(f"� Logs", key=f"logs_job_{i}_{agent_id}"):
                                                job_logs = job_manager.get_job_logs(job['id'], limit=5)
                                                if job_logs:
                                                    for log_entry in job_logs:
                                                        st.text(f"{log_entry['timestamp'][:16]} [{log_entry['event_type'].upper()}] {log_entry['message']}")
                                                else:
                                                    st.info("No logs found")
                                        with col_action3:
                                            if st.button(f"🗑️ Delete", key=f"delete_job_{i}_{agent_id}", type="secondary"):
                                                if job_manager.delete_job(job['id']):
                                                    st.success("✅ Deleted!")
                                                    st.rerun()
                                                else:
                                                    st.error("❌ Failed to delete")
                                        st.markdown("---")
                        
                        # Add new job form - using form instead of expander
                        st.markdown("**➕ Create New Job**")
                        
                        # Schedule configuration outside form to ensure visibility
                        st.markdown("**Job Configuration**")
                        
                        col_job1, col_job2 = st.columns(2)
                        with col_job1:
                            job_schedule_type = st.selectbox(
                                "Schedule Type",
                                options=["manual", "scheduled"],
                                index=0,
                                help="Manual: Run manually when needed. Scheduled: Run automatically at specified intervals.",
                                key=f"job_schedule_{agent_id}"
                            )
                            
                            # Initialize schedule variables
                            schedule_period = None
                            schedule_hour = None
                            schedule_minute = None
                            schedule_weekday = None
                            schedule_day = None
                            
                            if job_schedule_type == "scheduled":
                                # Schedule period selection
                                schedule_period = st.selectbox(
                                    "Schedule Period",
                                    options=["daily", "weekly", "monthly"],
                                    index=0,
                                    help="How often the job should run",
                                    key=f"job_period_{agent_id}"
                                )
                                
                                # Time selection (without nested columns)
                                st.markdown("**⏰ Execution Time:**")
                                schedule_hour = st.number_input(
                                    "Hour (24h)", 
                                    min_value=0, 
                                    max_value=23, 
                                    value=9, 
                                    key=f"job_hour_{agent_id}"
                                )
                                schedule_minute = st.number_input(
                                    "Minute", 
                                    min_value=0, 
                                    max_value=59, 
                                    value=0, 
                                    key=f"job_minute_{agent_id}"
                                )
                                
                                # Additional period-specific options
                                if schedule_period == "weekly":
                                    schedule_weekday = st.selectbox(
                                        "Day of Week",
                                        options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                                        index=0,
                                        help="Which day of the week to run",
                                        key=f"job_weekday_{agent_id}"
                                    )
                                elif schedule_period == "monthly":
                                    schedule_day = st.number_input(
                                    "Day of Month", 
                                        min_value=1, 
                                        max_value=28, 
                                        value=1, 
                                        help="Which day of the month to run (1-28 for safety)",
                                        key=f"job_day_{agent_id}"
                                    )
                                    
                                # Show schedule summary
                                if schedule_period == "daily":
                                    schedule_summary = f"Every day at {schedule_hour:02d}:{schedule_minute:02d}"
                                elif schedule_period == "weekly":
                                    schedule_summary = f"Every {schedule_weekday} at {schedule_hour:02d}:{schedule_minute:02d}"
                                else:  # monthly
                                    schedule_summary = f"Day {schedule_day} of every month at {schedule_hour:02d}:{schedule_minute:02d}"
                                
                                st.info(f"📅 **Schedule:** {schedule_summary}")
                        
                        with col_job2:
                            job_data_container = st.text_input(
                            "Data Container",
                                value=agent_config.get('data_container', ''),
                                placeholder="sales-data",
                                help="Blob container containing data files",
                                key=f"job_container_{agent_id}"
                            )
                            
                            job_data_files = st.text_area(
                                "Data Files (one per line)",
                                value=agent_config.get('data_file', ''),
                                placeholder="Sales Raw Data Final_v2.xlsx\nMonthly Report.xlsx",
                                help="List of files to upload to code interpreter",
                                key=f"job_files_{agent_id}"
                            )
                        
                        job_description = st.text_input(
                            "Job Description (optional)",
                            placeholder="Monthly data refresh job",
                            key=f"job_desc_{agent_id}"
                        )
                        
                        # Form for submit button only
                        with st.form(f"add_job_{agent_id}"):
                            st.markdown("**Create Job**")
                            
                            if st.form_submit_button("➕ Create Job", type="primary"):
                                # Get values from session state since form fields are outside
                                job_schedule_type = st.session_state.get(f"job_schedule_{agent_id}", "manual")
                                job_data_container = st.session_state.get(f"job_container_{agent_id}", "")
                                job_data_files = st.session_state.get(f"job_files_{agent_id}", "")
                                job_description = st.session_state.get(f"job_desc_{agent_id}", "")
                                
                                schedule_period = st.session_state.get(f"job_period_{agent_id}", "daily")
                                schedule_hour = st.session_state.get(f"job_hour_{agent_id}", 9)
                                schedule_minute = st.session_state.get(f"job_minute_{agent_id}", 0)
                                schedule_weekday = st.session_state.get(f"job_weekday_{agent_id}", "Monday")
                                schedule_day = st.session_state.get(f"job_day_{agent_id}", 1)
                                
                                if job_data_container and job_data_files:
                                    # Parse data files
                                    data_files_list = [f.strip() for f in job_data_files.split('\n') if f.strip()]
                                    
                                    # Get current agent type dynamically
                                    current_agent_type = agent_config.get('agent_type', 'Data Agent')
                                    
                                    job_config = {
                                        'agent_id': agent_id,
                                        'agent_type': current_agent_type,
                                        'schedule_type': job_schedule_type,
                                        'data_container': job_data_container,
                                        'data_files': data_files_list,
                                        'description': job_description
                                    }
                                    
                                    if job_schedule_type == "scheduled":
                                        job_config['schedule_period'] = schedule_period
                                        job_config['schedule_hour'] = schedule_hour
                                        job_config['schedule_minute'] = schedule_minute
                                        
                                        if schedule_period == "weekly":
                                            job_config['schedule_weekday'] = schedule_weekday
                                        elif schedule_period == "monthly":
                                            job_config['schedule_day'] = schedule_day
                                    
                                    if job_manager.create_job(job_config):
                                        st.success("✅ Job created successfully!")
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to create job")
                                else:
                                    st.error("❌ Please fill in Data Container and Data Files")
                    
                    except Exception as job_error:
                        st.error(f"❌ Job management error: {job_error}")
                        st.info("💡 Job management requires Azure Blob Storage connection")
            
            # Action buttons in a horizontal row
            button_col1, button_col2, button_col3, button_col4 = st.columns(4)
            
            with button_col1:
                if st.button(f"✏️ Edit Agent", key=f"edit_agent_{agent_id}"):
                    st.session_state[f"editing_agent_{agent_id}"] = True
                    st.rerun()
            
            with button_col2:
                if st.button("🔄 Job Configuration", key=f"show_job_config_{agent_id}"):
                    # Toggle Job Configuration visibility and make sure the expander stays open
                    st.session_state[f"show_jobs_{agent_id}"] = not st.session_state.get(
                        f"show_jobs_{agent_id}", False
                    )
                    st.session_state[expander_key] = True
                    st.rerun()
            
            with button_col3:
                # Status toggle
                new_status = "inactive" if status == "active" else "active"
                if st.button(f"{'⏸️' if status == 'active' else '▶️'} {new_status.title()}", key=f"toggle_{agent_id}"):
                    if blob_agent_manager.set_agent_status(agent_id, new_status):
                        # Clear session state agents to force refresh
                        if "agents" in st.session_state:
                            del st.session_state["agents"]
                        st.success(f"✅ Agent status updated to {new_status}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update agent status")
            
            with button_col4:
                # Delete agent
                if st.button(f"🗑️ Delete", key=f"delete_agent_{agent_id}", type="secondary"):
                    if blob_agent_manager.delete_agent(agent_id):
                        # Clear session state agents to force refresh
                        if "agents" in st.session_state:
                            del st.session_state["agents"]
                        st.success(f"🗑️ Agent {agent_id} deleted from blob storage!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete agent from blob storage")
            
            if st.session_state.get(f"editing_agent_{agent_id}", False):
                st.write("**Edit Agent Configuration (Will save to blob storage):**")
                with st.form(f"edit_agent_{agent_id}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_name = st.text_input("Name", value=agent_config.get('name', ''))
                        
                        # Agent Type Selection
                        current_agent_type = agent_config.get('agent_type', 'Data Agent')
                        edit_agent_type = st.selectbox(
                            "Agent Type",
                            options=["Data Agent", "Data Analyzer"],
                            index=0 if current_agent_type == "Data Agent" else 1,
                            help="Data Agent: Standard document-based agent. Data Analyzer: Uses Azure AI code interpreter for data analysis.",
                            key=f"edit_agent_type_{agent_id}"
                        )
                        
                        # Icon selector for editing
                        current_icon = agent_config.get('icon', '🤖')
                        edit_icon = show_icon_selector(default_icon=current_icon, key=f"edit_agent_{agent_id}")
                        
                        # Extract valid hex color from gradient or use default
                        color_value = agent_config.get('color', '#FF6B6B')
                        if color_value and '#' in color_value:
                            # Extract first hex color from gradient
                            import re
                            hex_match = re.search(r'#[0-9a-fA-F]{6}', color_value)
                            if hex_match:
                                color_value = hex_match.group()
                            else:
                                color_value = '#FF6B6B'
                        else:
                            color_value = '#FF6B6B'
                        edit_color = st.color_picker("Color", value=color_value)
                    
                    with col2:
                        edit_description = st.text_area("Description", value=agent_config.get('description', ''))
                        edit_connection_string = st.text_input("Connection String", 
                                                             value=agent_config.get('connection_string', ''),
                                                             placeholder="Azure AI connection string")
                        edit_agent_ai_id = st.text_input("AI Agent ID", 
                                                        value=agent_config.get('agent_id', ''),
                                                        placeholder="Assistant ID")
                        edit_container = st.text_input("Container Name", value=agent_config.get('container_name', ''))
                        edit_search_index = st.text_input("Search Index", value=agent_config.get('search_index', ''), 
                                                        help="Index name for search functionality")
                        edit_send_user_info = st.checkbox("Kullanıcı Bilgilerini Agent a Gönder", 
                                                           value=agent_config.get('send_user_info', False),
                                                           help="İşaretlenirse: giriş yapan kullanıcının Ad Soyad ve Email bilgisi her prompt'a eklenir.")
                        
                        # Data Analyzer configuration fields removed from edit form
                        edit_data_container = agent_config.get('data_container', '')
                        edit_data_file = agent_config.get('data_file', '')
                    
                    edit_categories = st.text_input("Categories (comma-separated)", 
                                                  value=', '.join(agent_config.get('categories', [])))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Save to Blob Storage", type="primary"):
                            updated_config = agent_config.copy()
                            updated_config.update({
                                "name": edit_name,
                                "icon": edit_icon,
                                "description": edit_description,
                                "connection_string": edit_connection_string,
                                "agent_id": edit_agent_ai_id,
                                "container_name": edit_container,
                                "search_index": edit_search_index,
                                "color": edit_color,
                                "categories": [cat.strip() for cat in edit_categories.split(",") if cat.strip()],
                                "agent_type": edit_agent_type,
                                # data_container/data_file intentionally not modified via UI
                                "send_user_info": edit_send_user_info
                            })
                            
                            if blob_agent_manager.update_agent(agent_id, updated_config):
                                st.session_state[f"editing_agent_{agent_id}"] = False
                                # Clear session state agents to force refresh
                                if "agents" in st.session_state:
                                    del st.session_state["agents"]
                                st.success("✅ Agent configuration updated and saved to blob storage!")
                                st.success("🔄 Agent cache cleared - dashboard will show updated agents")
                                st.rerun()
                            else:
                                st.error("❌ Failed to save agent configuration to blob storage")
                    with col2:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state[f"editing_agent_{agent_id}"] = False
                            st.rerun()
    
def show_agent_configuration_tab():
    """Agent configuration tab content"""
    st.subheader("🤖 Agent Configuration")
    
    # Safely get agents from session state
    agents = st.session_state.get("agents", {})
    
    # Ensure agents is a dictionary
    if not isinstance(agents, dict):
        st.warning("⚠️ Invalid agents data format. Resetting to empty dictionary.")
        agents = {}
        st.session_state.agents = agents
    
    # Current agents
    st.write("### 📋 Current Agents")
    if not agents:
        st.info("No agents configured yet. Add a new agent below.")
    else:
        for agent_id, agent_config in agents.items():
            with st.expander(f"🤖 {agent_config['name']} ({agent_id})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Basic Information:**")
                st.write(f"- **Name:** {agent_config['name']}")
                st.write(f"- **Type:** {agent_config.get('agent_type', 'Data Agent')}")
                st.write(f"- **Description:** {agent_config['description']}")
                st.write(f"- **Icon:** {agent_config['icon']}")
                st.write(f"- **Color:** {agent_config['color']}")
                
            with col2:
                st.write("**Azure Configuration:**")
                st.write(f"- **Container:** {agent_config['container_name']}")
                st.write(f"- **Connection String:** {agent_config['connection_string'][:30]}...")
                st.write(f"- **Agent ID:** {agent_config['agent_id']}")
                
                # Data Analyzer configuration display removed from summary
            
            # Edit agent button
            if st.button(f"✏️ Edit Agent", key=f"edit_agent_{agent_id}"):
                st.session_state[f"editing_agent_{agent_id}"] = True
                st.rerun()
            
            # Edit agent form
            if st.session_state.get(f"editing_agent_{agent_id}", False):
                with st.form(f"edit_agent_form_{agent_id}"):
                    st.write("**Edit Agent Configuration:**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Name", value=agent_config['name'], key=f"edit_name_{agent_id}")
                        new_description = st.text_area("Description", value=agent_config['description'], key=f"edit_desc_{agent_id}")
                        
                        # Agent Type Selection
                        current_agent_type = agent_config.get('agent_type', 'Data Agent')
                        new_agent_type = st.selectbox(
                            "Agent Type",
                            options=["Data Agent", "Data Analyzer"],
                            index=0 if current_agent_type == "Data Agent" else 1,
                            help="Data Agent: Standard document-based agent. Data Analyzer: Uses Azure AI code interpreter for data analysis.",
                            key=f"edit_agent_type_regular_{agent_id}"
                        )
                        
                        # Icon selector for editing (second form) - use radio for better form experience
                        current_icon = agent_config.get('icon', '🤖')
                        new_icon = show_icon_selector(default_icon=current_icon, key=f"edit_agent_form_{agent_id}", use_radio=True)
                        
                        # Extract valid hex color from gradient or use default
                        color_value = agent_config.get('color', '#FF6B6B')
                        if color_value and '#' in color_value:
                            # Extract first hex color from gradient
                            import re
                            hex_match = re.search(r'#[0-9a-fA-F]{6}', color_value)
                            if hex_match:
                                color_value = hex_match.group()
                            else:
                                color_value = '#FF6B6B'
                        else:
                            color_value = '#FF6B6B'
                        new_color = st.color_picker("Color", value=color_value, key=f"edit_color_{agent_id}")
                    
                    with col2:
                        new_container = st.text_input("Container Name", value=agent_config['container_name'], key=f"edit_container_{agent_id}")
                        new_connection_string = st.text_input("Azure Connection String", value=agent_config['connection_string'], type="password", key=f"edit_conn_{agent_id}")
                        new_agent_id = st.text_input("Agent ID", value=agent_config['agent_id'], key=f"edit_agent_id_{agent_id}")
                        new_search_index = st.text_input("Search Index", value=agent_config.get('search_index', ''), 
                                                        key=f"edit_search_{agent_id}", 
                                                        help="Index name for search functionality")
                        new_send_user_info = st.checkbox("Kullanıcı Bilgilerini Agent a Gönder", 
                                                          value=agent_config.get('send_user_info', False),
                                                          key=f"edit_send_user_info_{agent_id}",
                                                          help="İşaretlenirse: giriş yapan kullanıcının Ad Soyad ve Email bilgisi her prompt'a eklenir.")
                        
                        # Data Analyzer specific fields removed from edit form
                        new_data_container = agent_config.get('data_container', '')
                        new_data_file = agent_config.get('data_file', '')
                    
                    new_categories = st.text_input("Categories (comma-separated)", 
                                                  value=', '.join(agent_config.get('categories', [])),
                                                  key=f"edit_categories_{agent_id}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Save Changes", type="primary"):
                            # Ensure agents dict exists
                            if "agents" not in st.session_state:
                                st.session_state.agents = {}
                            
                            # Update agent configuration
                            if agent_id in st.session_state.agents:
                                st.session_state.agents[agent_id].update({
                                    "name": new_name,
                                    "description": new_description,
                                    "icon": new_icon,
                                    "color": new_color,
                                "container_name": new_container,
                                "search_index": new_search_index,
                                "connection_string": new_connection_string,
                                "agent_id": new_agent_id,
                                "categories": [cat.strip() for cat in new_categories.split(",") if cat.strip()],
                                "agent_type": new_agent_type,
                                # data_container/data_file intentionally not modified via UI
                                "send_user_info": new_send_user_info
                            })
                            st.session_state[f"editing_agent_{agent_id}"] = False
                            st.success("✅ Agent configuration updated!")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state[f"editing_agent_{agent_id}"] = False
                            st.rerun()
            
            # Delete agent button
            if st.button(f"🗑️ Delete Agent", key=f"delete_agent_{agent_id}", type="secondary"):
                if st.session_state.get(f"confirm_delete_{agent_id}", False):
                    # Ensure agents dict exists and agent is in it
                    if "agents" in st.session_state and agent_id in st.session_state.agents:
                        del st.session_state.agents[agent_id]
                        st.success(f"🗑️ Agent {agent_config['name']} deleted!")
                        st.rerun()
                    else:
                        st.error("Agent not found for deletion")
                else:
                    st.session_state[f"confirm_delete_{agent_id}"] = True
                    st.warning("⚠️ Click again to confirm deletion")
    
    # Add new agent section
    st.markdown("---")
    st.subheader("➕ Add New Agent")
    
    with st.form("add_agent"):
        col1, col2 = st.columns(2)
        
        with col1:
            agent_name = st.text_input("Agent Name")
            agent_description = st.text_area("Description")
            
            # Agent Type Selection
            agent_type = st.selectbox(
                "Agent Type",
                options=["Data Agent", "Data Analyzer"],
                index=0,
                help="Data Agent: Standard document-based agent. Data Analyzer: Uses Azure AI code interpreter for data analysis.",
                key="add_agent_type_regular"
            )
            
            # Icon selector for third form - use radio for better form experience
            agent_icon = show_icon_selector(default_icon="🤖", key="add_agent_third", use_radio=True)
            
            agent_color = st.color_picker("Color", value="#0078d4")
        
        with col2:
            container_name = st.text_input("Container Name")
            connection_string = st.text_input("Azure Connection String", type="password")
            agent_id = st.text_input("Agent ID")
            add_send_user_info = st.checkbox("Kullanıcı Bilgilerini Agent a Gönder", value=False,
                                             help="İşaretlenirse: giriş yapan kullanıcının Ad Soyad ve Email bilgisi her prompt'a eklenir.")
            
            # Data Analyzer specific fields
            if agent_type == "Data Analyzer":
                st.markdown("**Data Analyzer Configuration:**")
                data_container = st.text_input("Data Container", placeholder="sales-data", 
                                             help="Blob container containing data files for analysis")
                data_file = st.text_input("Data File", placeholder="Sales Raw Data Final_v2.xlsx", 
                                        help="Specific file to load into code interpreter")
            else:
                data_container = ""
                data_file = ""
        
        categories = st.text_input("Categories (comma-separated)", placeholder="e.g., documents, reports, policies")
        
        if st.form_submit_button("Add Agent", type="primary"):
            if agent_name and container_name and connection_string and agent_id:
                new_agent_id = agent_name.lower().replace(" ", "_")
                
                if new_agent_id not in agents:
                    # Ensure agents dict exists
                    if "agents" not in st.session_state:
                        st.session_state.agents = {}
                    
                    st.session_state.agents[new_agent_id] = {
                        "name": agent_name,
                        "description": agent_description,
                        "icon": agent_icon,
                        "color": agent_color,
                        "container_name": container_name,
                        "search_index": "",  # Empty since search is disabled
                        "azure_connection_string": connection_string,
                        "agent_id": agent_id,
                        "categories": [cat.strip() for cat in categories.split(",") if cat.strip()],
                        "agent_type": agent_type,
                        "data_container": data_container,
                        "data_file": data_file,
                        "send_user_info": add_send_user_info
                    }
                    st.success(f"✅ Agent {agent_name} added successfully!")
                    st.rerun()
                else:
                    st.error("❌ Agent with this name already exists")
            else:
                st.error("❌ Please fill in all required fields")

def show_system_settings_tab():
    """System settings tab content"""
    st.subheader("🔧 System Settings")
    
    # User Management (only for admins)
    if st.session_state.user_role == "admin":
        st.write("### 👥 User Management")
        
        # Check if user_manager is available
        if st.session_state.user_manager is None:
            st.error("❌ User management is currently disabled due to Azure connection issues.")
            st.info("💡 User management requires Azure Blob Storage connection. Please check your Azure configuration.")
            return
        
        # User list
        try:
            users = st.session_state.user_manager.get_all_users()
            # Exclude activity log users
            if isinstance(users, dict):
                users = {u: d for u, d in users.items() if not str(u).startswith("activiy_admin")}
        except Exception as e:
            st.error(f"❌ Error loading users: {e}")
            users = {}
        
        if users:
            st.write("**Current Users:**")
            user_df = pd.DataFrame([
                {
                    "Username": username,
                    "Role": user_data.get("role", "unknown"),
                    "Created": user_data.get("created_at", "unknown"),
                    "Permissions Count": len(user_data.get("permissions", []))
                }
                for username, user_data in users.items()
            ])
            st.dataframe(user_df)
        
        # Actions for user management are now centralized in the User Management tab
        st.info("ℹ️ Kullanıcı ekleme/düzenleme/silme ve sistem sıfırlama işlemleri 'User Management' sekmesine taşındı.")
    
    # Azure Configuration
    st.write("### ☁️ Azure Configuration")
    with st.expander("Azure Service Settings"):
        st.write("**Current Azure Configuration:**")
        import os as _os
        _cid = _os.environ.get("AZURE_CLIENT_ID", "NOT_SET")
        _tid = _os.environ.get("AZURE_TENANT_ID", "NOT_SET")
        _redir = _os.environ.get("REDIRECT_URI", "NOT_SET")
        _mi = _os.environ.get("USE_MANAGED_IDENTITY", "false")
        _acct = _os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "-")
        _cstr = _os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "-")
        _sec = _os.environ.get("AZURE_CLIENT_SECRET")
        _sec_mask = (_sec[:4] + "..." + _sec[-4:]) if _sec and len(_sec) > 12 else ("SET" if _sec else "NOT_SET")
        st.code(f"""
AZURE_CLIENT_ID={_cid}
AZURE_CLIENT_SECRET={_sec_mask}
AZURE_TENANT_ID={_tid}
REDIRECT_URI={_redir}
USE_MANAGED_IDENTITY={_mi}
AZURE_STORAGE_ACCOUNT_NAME={_acct}
AZURE_STORAGE_CONNECTION_STRING={(_cstr[:30] + '...') if _cstr and len(_cstr)>40 else _cstr}
        """)

        st.info("💡 Azure configuration is managed through environment variables. Contact your system administrator to modify these settings.")
    
    # Application Settings
    st.write("### 📱 Application Settings")
    with st.form("app_settings"):
        st.write("**General Settings:**")
        max_file_size = st.number_input("Max File Size (MB)", value=10, min_value=1, max_value=100)
        session_timeout = st.number_input("Session Timeout (minutes)", value=60, min_value=15, max_value=480)
        auto_save_interval = st.number_input("Auto-save Interval (seconds)", value=30, min_value=10, max_value=300)
        
        st.write("**Chat Settings:**")
        max_message_length = st.number_input("Max Message Length", value=4000, min_value=100, max_value=10000)
        chat_history_limit = st.number_input("Chat History Limit", value=50, min_value=10, max_value=200)
        
        st.write("**Document Settings:**")
        supported_formats = st.multiselect("Supported File Formats", 
                                         options=["pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx"], 
                                         default=["pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx"])
        
        if st.form_submit_button("💾 Save Settings", type="primary"):
            # Save settings to session state (in a real app, these would be saved to database)
            st.session_state.application_settings = {
                "max_file_size": max_file_size,
                "session_timeout": session_timeout,
                "auto_save_interval": auto_save_interval,
                "max_message_length": max_message_length,
                "chat_history_limit": chat_history_limit,
                "supported_formats": supported_formats
            }
            st.success("✅ Settings saved successfully!")
    
    # System Information
    st.write("### 📊 System Information")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        agents_count = len(st.session_state.get("agents", {}))
        st.metric("Total Agents", agents_count)
    with col2:
        users_count = len(st.session_state.user_manager.get_all_users()) if st.session_state.user_manager else 0
        st.metric("Total Users", users_count)
    with col3:
        st.metric("Active Sessions", 1)  # This would be dynamic in a real app
    
    # Backup and Restore
    st.write("### 💾 Backup & Restore")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Export Configuration", type="secondary"):
            import json
            config_data = {
                "agents": st.session_state.get("agents", {}),
                "users": st.session_state.user_manager.get_all_users() if st.session_state.user_manager else {},
                "settings": st.session_state.get("app_settings", {})
            }
            st.download_button(
                label="💾 Download Config",
                data=json.dumps(config_data, indent=2),
                file_name=f"azure_ai_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    with col2:
        uploaded_config = st.file_uploader("📤 Import Configuration", type="json")
        if uploaded_config and st.button("🔄 Restore Configuration"):
            try:
                import json
                config_data = json.load(uploaded_config)
                
                if "agents" in config_data:
                    # Ensure we always have a dictionary format
                    agents_data = config_data["agents"]
                    if isinstance(agents_data, dict):
                        st.session_state.agents = agents_data
                    elif isinstance(agents_data, list):
                        # Convert list to dict if needed (legacy format)
                        st.session_state.agents = {f"agent_{i}": agent for i, agent in enumerate(agents_data)}
                    else:
                        st.warning("Invalid agents format in configuration file")
                        st.session_state.agents = {}
                if "users" in config_data and st.session_state.user_manager is not None:
                    # For blob storage user manager, we need to update users individually
                    try:
                        existing_users = st.session_state.user_manager.get_all_users()
                        for username, user_data in config_data["users"].items():
                            if username not in existing_users:
                                st.session_state.user_manager.add_user(
                                    username, 
                                    user_data.get("role", "standard"),
                                    user_data.get("permissions", {})
                                )
                    except Exception as e:
                        st.error(f"❌ Error importing users: {e}")
                elif "users" in config_data:
                    st.warning("⚠️ Cannot import users: User management is disabled due to Azure connection issues.")
                if "settings" in config_data:
                    st.session_state.app_settings = config_data["settings"]
                
                st.success("✅ Configuration restored successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error restoring configuration: {str(e)}")

def show_azure_ai_agents_list():
    """Display available Azure AI agents from Azure AI Projects"""
    st.subheader("🤖 Available Azure AI Agents")
    
    try:
        # Get Azure configuration
        from azure_utils import AzureConfig, EnhancedAzureAIAgentClient
        config = AzureConfig()
        
        # Create a client to list agents
        client = EnhancedAzureAIAgentClient("", "", config, "")  # Pass empty container name
        agents = client.get_available_agents()
        
        if agents:
            st.success(f"✅ Found {len(agents)} Azure AI agents")
            
            # Display agents in cards
            for agent in agents:
                with st.expander(f"🤖 {agent['name']} (ID: {agent['id'][:12]}...)"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Model:** {agent.get('model', 'Unknown')}")
                        st.write(f"**Description:** {agent.get('description', 'No description')}")
                        if agent.get('instructions'):
                            st.write(f"**Instructions:** {agent['instructions'][:100]}...")
                        
                        # Created date
                        if agent.get('created_at'):
                            try:
                                import datetime
                                created_date = datetime.datetime.fromtimestamp(agent['created_at'])
                                st.write(f"**Created:** {created_date.strftime('%Y-%m-%d %H:%M')}")
                            except:
                                st.write(f"**Created:** {agent['created_at']}")
                    
                    with col2:
                        st.write("**Agent ID:**")
                        st.code(agent['id'], language="text")
                        
                        if st.button(f"Select Agent", key=f"select_{agent['id']}"):
                            st.session_state.selected_agent_id = agent['id']
                            st.success(f"✅ Selected agent: {agent['name']}")
                            st.rerun()
                            
        else:
            st.warning("⚠️ No Azure AI agents found. Please create agents in Azure AI Projects first.")
            st.info("💡 You can create agents in the Azure AI Projects portal.")
            
    except Exception as e:
        st.error(f"❌ Error connecting to Azure AI Projects: {str(e)}")
        st.info("💡 Please check your Azure AI Projects configuration in the environment settings.")

def show_azure_ai_agents_list():
    """Display available Azure AI agents from Azure AI Projects"""
    try:
        from azure_utils import AzureConfig, EnhancedAzureAIAgentClient
        
        # Try to get a working AI client
        azure_config = AzureConfig()
        
        # Create a test client with working configuration
        try:
            ai_client = EnhancedAzureAIAgentClient(
                connection_string="test",  # Will be ignored in direct initialization
                agent_id="test",  # Will be ignored
                config=azure_config,
                container_name=""  # Pass empty container name
            )
            
            # Get available agents
            azure_agents = ai_client.get_available_agents()
            
            if azure_agents:
                st.success(f"✅ Found {len(azure_agents)} Azure AI agents")
                
                # Display agents in cards
                cols = st.columns(min(len(azure_agents), 3))
                for i, agent in enumerate(azure_agents):
                    with cols[i % 3]:
                        with st.container():
                            st.markdown(f"""
                            <div class="agent-card">
                                <div class="agent-icon">🤖</div>
                                <div class="agent-title">{agent['name']}</div>
                                <div class="agent-description">{agent['description']}</div>
                                <div class="agent-stats">
                                    <strong>ID:</strong> {agent['id'][:20]}...<br>
                                    <strong>Model:</strong> {agent['model']}<br>
                                    <strong>Created:</strong> {datetime.fromtimestamp(agent['created_at']).strftime('%Y-%m-%d') if agent['created_at'] else 'Unknown'}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button(f"Open {agent['name']}", key=f"open_azure_{agent['id']}"):
                                # Set up the agent for chat
                                st.session_state.selected_agent = {
                                    'id': agent['id'],
                                    'name': agent['name'],
                                    'type': 'azure_ai_projects',
                                    'agent_id': agent['id'],
                                    'connection_string': 'azure_ai_projects',
                                    'description': agent['description']
                                }
                                st.session_state.current_page = "agent_interface"
                                st.rerun()
            else:
                st.warning("⚠️ No Azure AI agents found. Please create agents in Azure AI Projects first.")
                st.info("💡 You can create agents in the Azure AI Projects portal.")
                
        except Exception as client_error:
            st.error(f"❌ Error connecting to Azure AI Projects: {client_error}")
            st.info("💡 Please check your Azure AI Projects configuration.")
            
    except ImportError:
        st.error("❌ Azure utilities not available")
    except Exception as e:
        st.error(f"❌ Error loading Azure AI agents: {e}")

def show_connection_status():
    """Show Azure services connection status"""
    st.subheader("🔗 Azure Services Status")
    
    try:
        from azure_utils import AzureConfig
        config = AzureConfig()
        
        # Test Azure services
        status_data = []
        
        # Test Blob Storage
        try:
            from azure.storage.blob import BlobServiceClient
            if config.storage_connection_string and "DefaultEndpointsProtocol" in config.storage_connection_string:
                blob_client = BlobServiceClient.from_connection_string(config.storage_connection_string)
                containers = list(blob_client.list_containers())
                status_data.append({"Service": "Azure Blob Storage", "Status": "✅ Connected", "Details": f"{len(containers)} containers"})
            else:
                status_data.append({"Service": "Azure Blob Storage", "Status": "❌ Not configured", "Details": "Missing connection string"})
        except Exception as e:
            status_data.append({"Service": "Azure Blob Storage", "Status": "❌ Error", "Details": str(e)[:50]})
        
        # Test Azure Search
        try:
            if config.search_endpoint and config.search_admin_key:
                from azure.search.documents.indexes import SearchIndexClient
                from azure.core.credentials import AzureKeyCredential
                
                # Add timeout and retry configuration
                from azure.core.pipeline.policies import RetryPolicy
                search_client = SearchIndexClient(
                    endpoint=config.search_endpoint,
                    credential=AzureKeyCredential(config.search_admin_key),
                    retry_policy=RetryPolicy(total_retries=1)
                )
                
                # Use timeout for the list operation
                try:
                    indexes = list(search_client.list_indexes())
                    index_names = [idx.name for idx in indexes if hasattr(idx, 'name')]
                    status_data.append({"Service": "Azure AI Search", "Status": "✅ Connected", "Details": f"{len(indexes)} indexes: {', '.join(index_names[:2])}"})
                except Exception as list_error:
                    # If listing fails, try a simpler connectivity test
                    status_data.append({"Service": "Azure AI Search", "Status": "⚠️ Limited", "Details": f"Connected but listing failed: {str(list_error)[:50]}"})
            else:
                status_data.append({"Service": "Azure AI Search", "Status": "❌ Not configured", "Details": "Missing endpoint/key"})
        except Exception as e:
            status_data.append({"Service": "Azure AI Search", "Status": "❌ Error", "Details": str(e)[:50]})
        
        # Test Azure AI Projects
        try:
            from azure_utils import EnhancedAzureAIAgentClient
            client = EnhancedAzureAIAgentClient("", "", config, "")  # Pass empty container name
            agents = client.get_available_agents()
            status_data.append({"Service": "Azure AI Projects", "Status": "✅ Connected", "Details": f"{len(agents)} agents"})
        except Exception as e:
            status_data.append({"Service": "Azure AI Projects", "Status": "❌ Error", "Details": str(e)[:50]})
        
        # Display status table
        df = pd.DataFrame(status_data)
        st.dataframe(df)
        
    except Exception as e:
        st.error(f"❌ Error checking Azure services: {str(e)}")

def show_azure_ai_agents_list():
    """Show available Azure AI Project agents"""
    try:
        from azure_utils import AzureConfig, EnhancedAzureAIAgentClient
        config = AzureConfig()
        
        # Create a temporary client to get Azure AI agents
        temp_client = EnhancedAzureAIAgentClient("", "", config, "")  # Pass empty container name
        azure_agents = temp_client.get_available_agents()
        
        if azure_agents:
            st.success(f"✅ Found {len(azure_agents)} Azure AI agents available")
            
            # Display agents in cards
            cols = st.columns(3)
            for idx, agent in enumerate(azure_agents):
                col = cols[idx % 3]
                
                with col:
                    st.markdown(f"""
                    <div class="agent-card">
                        <div class="agent-icon">🤖</div>
                        <div class="agent-title">{agent['name']}</div>
                        <div class="agent-description">{agent.get('description', 'Azure AI Agent')}</div>
                        <div class="agent-stats">
                            <small>
                                🔧 Model: {agent['model']}<br>
                                🆔 ID: {agent['id'][:20]}...
                            </small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"Connect to {agent['name']}", key=f"connect_{agent['id']}", type="primary"):
                        st.session_state.selected_agent = agent['id']  # Use consistent variable name
                        st.session_state.selected_azure_agent = agent  # Keep backup for compatibility  
                        st.session_state.current_page = "azure_agent_interface"
                        st.rerun()
        else:
            st.warning("⚠️ No Azure AI agents found. Please check your Azure AI Projects configuration.")
            st.info("📋 Environment variables needed:")
            st.code("""
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret  
AZURE_TENANT_ID=your_tenant_id
AZURE_SUBSCRIPTION_ID=your_subscription_id
AZURE_RESOURCE_GROUP_NAME=your_resource_group
AZURE_AI_PROJECT_NAME=your_project_name
            """)
            
    except Exception as e:
        st.error(f"❌ Error loading Azure AI agents: {str(e)}")
        st.info("💡 This might be due to:")
        st.write("• Missing Azure AI Projects configuration")
        st.write("• Invalid credentials")
        st.write("• Network connectivity issues")
        st.write("• Azure AI Projects service not available")
