import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os
import io
import hashlib
import time
from datetime import datetime

# ================= CONFIGURATION SÉCURITÉ =================
# ⚠️ CHANGEZ CE MOT DE PASSE ! ⚠️
APP_PASSWORD = "Indigo2025**"  # À MODIFIER !
PASSWORD_HASH = hashlib.sha256(APP_PASSWORD.encode()).hexdigest()

# LIMITES DE SÉCURITÉ (SANS BLOCAGE, SEULEMENT WARNING)
MAX_FILES = 10
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB
# ==========================================================

# 🔐 SYSTÈME D'AUTHENTIFICATION
def check_authentication():
    """Vérifie si l'utilisateur est authentifié"""
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.auth_time = None
    
    if st.session_state.authenticated and st.session_state.auth_time:
        session_duration = time.time() - st.session_state.auth_time
        if session_duration < 4 * 3600:
            return True
        else:
            st.session_state.authenticated = False
            st.session_state.auth_time = None
    
    return False

def show_login_page():
    """Affiche la page de connexion"""
    st.set_page_config(
        page_title="Authentification",
        page_icon="🔒",
        layout="centered"
    )
    
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            border-radius: 10px;
            background-color: #ffffff;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown('<div style="text-align: center; margin-bottom: 2rem;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 2rem; font-weight: bold; color: #1E3A8A;">🔒 XML/Excel</div>', unsafe_allow_html=True)
    st.markdown('<h3 style="text-align: center; color: #1E3A8A;">Authentification</h3>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">INDIGO COMPANY / INDITEX</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    password = st.text_input("**Mot de passe :**", type="password", key="login_password")
    
    if st.button("🔓 Se connecter", type="primary", use_container_width=True):
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        if input_hash == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.session_state.auth_time = time.time()
            st.success("✅ Connexion réussie !")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Mot de passe incorrect")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

if not check_authentication():
    show_login_page()

# ================= FONCTIONS PRINCIPALES =================

def validate_files(files):
    """Validation simple des fichiers (sans blocage)"""
    valid_files = []
    
    # Filtrer uniquement les fichiers XML
    for file in files:
        if file.name.lower().endswith('.xml'):
            valid_files.append(file)
    
    return valid_files

def detect_xml_format(xml_content):
    """Détecte le format du fichier XML"""
    try:
        root = ET.fromstring(xml_content)
        root_tag = root.tag
        
        if 'ITX_CLOSE_EXPORT_COM' in root_tag:
            return 'ITX_COM'
        elif 'ITXCloseExport' in root_tag or 'ITX_CLOSE_EXPORT' in root_tag:
            return 'ITX_STANDARD'
        else:
            if root.find('.//SALE_LINE_ITEMS') is not None:
                return 'ITX_COM'
            elif root.find('.//SALE_LINES') is not None:
                return 'ITX_STANDARD'
            else:
                return 'UNKNOWN'
    except:
        return 'UNKNOWN'

def parse_itx_com_format(xml_content):
    """Parse le format ITX_CLOSE_EXPORT_COM"""
    try:
        root = ET.fromstring(xml_content)
        dataframes = {}

        def extract_itx_com_section(section_name, element_name):
            data = []
            section = root.find(f'.//{section_name}')
            
            if section is not None:
                elements = section.findall(element_name)
                for elem in elements:
                    row = {}
                    for child in elem:
                        text = child.text
                        if text is not None:
                            if text.strip().isdigit() or (text.strip().startswith('-') and text.strip()[1:].isdigit()):
                                try:
                                    row[child.tag] = int(text)
                                except:
                                    row[child.tag] = text
                            else:
                                row[child.tag] = text
                        else:
                            row[child.tag] = None
                    data.append(row)
            
            if data:
                return pd.DataFrame(data)
            return pd.DataFrame()

        # Sections
        sections = [
            ('VALID_TICKETS', 'TICKET'),
            ('SALE_LINE_ITEMS', 'ITEM'),
            ('MEDIA_LINES', 'MEDIA'),
            ('CUSTOMER_TICKETS', 'CT_TICKET')
        ]
        
        for section_name, element_name in sections:
            df = extract_itx_com_section(section_name, element_name)
            if not df.empty:
                dataframes[section_name] = df

        return dataframes

    except Exception as e:
        return {}

def parse_standard_format(xml_content):
    """Parse le format standard ItxCloseExport"""
    try:
        root = ET.fromstring(xml_content)
        dataframes = {}

        def extract_section(xpath, element_name, attributes=None, fields=None):
            data = []
            elements = root.findall(xpath)

            for elem in elements:
                row = {}
                if attributes:
                    for attr in attributes:
                        row[attr] = elem.get(attr)
                if fields:
                    for field in fields:
                        field_elem = elem.find(field)
                        row[field] = field_elem.text if field_elem is not None else None
                data.append(row)

            if data:
                return pd.DataFrame(data)
            return pd.DataFrame()

        # Configuration des sections
        sections_config = [
            ('.//SALE_LINES/LINE', 'LINE', 
             ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER'],
             ['barcode', 'description', 'quantity', 'price', 'orgPrice', 'date', 'time', 
              'familyCode', 'subFamilyCode', 'isVoidLine', 'lineNumber', 'campaign', 
              'lineType', 'employeeId', 'campaignYear', 'period', 'departmentId', 
              'operationTypeGroup', 'controlCode']),
              
            ('.//VALID_TICKETS/TICKET', 'TICKET',
             ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER', 'DOCUMENTUUID'],
             ['serial', 'date', 'time', 'operatorId', 'totalSale', 'totalNet',
              'isVoidTicket', 'employeeId', 'fiscalprinterId', 'operationTypeGroup', 'roundingError']),
              
            ('.//MEDIA_LINES/MEDIA', 'MEDIA',
             ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER'],
             ['serial', 'date', 'time', 'paid', 'returned', 'paymentMethod']),
              
            ('.//VOIDED_TICKETS/TICKET_VOID', 'TICKET_VOID',
             ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER', 'DOCUMENTUUID'],
             ['time', 'operatorId', 'voidedserial', 'voidedoperationNumber',
              'voidedPosNumber', 'voidedstoreId', 'originalUID']),
              
            ('.//TRANSACTIONS/TRANSACTION', 'TRANSACTION', None,
             ['code', 'description', 'debit', 'credit', 'auxValue', 'auxValue2',
              'taxPercent', 'employeeId', 'universalId', 'txType']),
              
            ('.//WARNINGS/WARNING', 'WARNING', None,
             ['warningType', 'warningMessage', 'posNumber', 'refoperationNumber'])
        ]
        
        for xpath, element_name, attrs, fields in sections_config:
            df = extract_section(xpath, element_name, attrs, fields)
            if not df.empty:
                dataframes[element_name if element_name != 'LINE' else 'SALE_LINES'] = df

        # STORE_INFO
        store_info = root.find('.//STORE_INFO')
        if store_info is not None:
            store_data = {
                'storeId': store_info.findtext('storeId'),
                'companyName': store_info.findtext('companyName'),
                'fiscalIdentifier': store_info.findtext('fiscalIdentifier'),
                'sessionDate': store_info.findtext('sessionDate'),
                'dateFrom': store_info.findtext('dateFrom'),
                'timeFrom': store_info.findtext('timeFrom'),
                'dateTo': store_info.findtext('dateTo'),
                'timeTo': store_info.findtext('timeTo'),
                'version': store_info.findtext('version')
            }
            dataframes['STORE_INFO'] = pd.DataFrame([store_data])

        return dataframes

    except Exception as e:
        return {}

def parse_xml_to_dataframes(xml_content):
    """Détecte le format et parse le contenu XML"""
    try:
        xml_format = detect_xml_format(xml_content)
        
        if xml_format == 'ITX_COM':
            return parse_itx_com_format(xml_content), xml_format
        elif xml_format == 'ITX_STANDARD':
            return parse_standard_format(xml_content), xml_format
        else:
            data_com = parse_itx_com_format(xml_content)
            data_std = parse_standard_format(xml_content)
            
            total_com = sum(len(df) for df in data_com.values())
            total_std = sum(len(df) for df in data_std.values())
            
            if total_com > total_std:
                return data_com, 'ITX_COM (auto-détecté)'
            elif total_std > 0:
                return data_std, 'ITX_STANDARD (auto-détecté)'
            else:
                return {}, 'INCONNU'
                
    except Exception as e:
        return {}, 'ERREUR'

def create_excel_file(dataframes):
    """Crée un fichier Excel en mémoire"""
    output = io.BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in dataframes.items():
                if not df.empty:
                    sheet_name_clean = sheet_name[:31]
                    df.to_excel(writer, sheet_name=sheet_name_clean, index=False)
        
        output.seek(0)
        return output
    except Exception as e:
        return None

# ================= APPLICATION PRINCIPALE =================
st.set_page_config(
    page_title="XML/Excel",
    page_icon="🔄",
    layout="wide"
)

# CSS simple
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # En-tête
    st.markdown('<h1 class="main-header">🔄 XML/Excel</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; margin-bottom: 2rem;">INDIGO COMPANY / INDITEX</p>', unsafe_allow_html=True)

    # Sidebar simple
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        
        # Info session
        if st.session_state.get("auth_time"):
            elapsed = time.time() - st.session_state.auth_time
            remaining = max(0, 4*3600 - elapsed)
            minutes = int(remaining // 60)
            st.caption(f"⏱️ Session: {minutes}min restant(s)")
        
        # Déconnexion
        if st.button("🚪 Déconnexion", type="secondary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_time = None
            st.rerun()

    # Zone d'upload
    st.markdown("### 📁 Upload de fichiers")
    
    uploaded_files = st.file_uploader(
        "Sélectionnez vos fichiers XML",
        type=['xml'],
        accept_multiple_files=True
    )

    if uploaded_files:
        # Validation simple sans message d'erreur
        valid_files = [f for f in uploaded_files if f.name.lower().endswith('.xml')]
        
        if valid_files:
            st.success(f"✅ {len(valid_files)} fichier(s) XML détecté(s)")
        else:
            st.warning("⚠️ Aucun fichier XML valide trouvé")

    # Traitement
    if uploaded_files and valid_files:
        st.markdown("---")
        st.markdown("### ⚡ Traitement")
        
        if st.button("🚀 Traiter les fichiers", type="primary"):
            results = {}
            format_info = {}
            
            with st.spinner("Traitement en cours..."):
                progress_bar = st.progress(0)
                
                for idx, file_obj in enumerate(valid_files):
                    try:
                        progress_bar.progress((idx + 1) / len(valid_files))
                        
                        content = file_obj.getvalue().decode('utf-8')
                        dataframes, xml_format = parse_xml_to_dataframes(content)
                        
                        if dataframes:
                            excel_file = create_excel_file(dataframes)
                            
                            if excel_file:
                                results[file_obj.name] = {
                                    'excel_data': excel_file,
                                    'row_count': sum(len(df) for df in dataframes.values()),
                                    'section_count': len(dataframes)
                                }
                                format_info[file_obj.name] = xml_format
                    
                    except Exception:
                        continue
                
                progress_bar.empty()
                
                if results:
                    st.markdown("---")
                    st.markdown("### 💾 Téléchargements")
                    
                    # Résumé
                    total_files = len(results)
                    total_rows = sum(info['row_count'] for info in results.values())
                    
                    st.info(f"📊 **Résumé :** {total_files} fichier(s) traité(s), {total_rows:,} lignes extraites")
                    
                    # Téléchargements
                    for file_name, file_info in results.items():
                        base_name = os.path.splitext(file_name)[0]
                        excel_data = file_info['excel_data']
                        
                        if excel_data:
                            st.download_button(
                                label=f"📥 Télécharger {file_name}.xlsx",
                                data=excel_data,
                                file_name=f"{base_name}_export.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_{hashlib.md5(file_name.encode()).hexdigest()[:8]}"
                            )
                    
                    st.success("✅ Traitement terminé avec succès !")
                else:
                    st.warning("⚠️ Aucune donnée n'a pu être extraite")

if __name__ == "__main__":
    main()
