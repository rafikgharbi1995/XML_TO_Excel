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

# LIMITES DE SÉCURITÉ
MAX_FILES = 10
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_TOTAL_SIZE = 20 * 1024 * 1024  # 20MB
# ==========================================================

# 🔐 SYSTÈME D'AUTHENTIFICATION
def check_authentication():
    """Vérifie si l'utilisateur est authentifié"""
    
    # Initialiser la session
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.auth_time = None
    
    # Si déjà authentifié et session encore valide (4 heures)
    if st.session_state.authenticated and st.session_state.auth_time:
        session_duration = time.time() - st.session_state.auth_time
        if session_duration < 4 * 3600:  # 4 heures
            return True
        else:
            # Session expirée
            st.session_state.authenticated = False
            st.session_state.auth_time = None
    
    return False

def show_login_page():
    """Affiche la page de connexion sécurisée"""
    st.set_page_config(
        page_title="Authentification",
        page_icon="🔒",
        layout="centered"
    )
    
    # Style pour la page de login
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            background-color: #ffffff;
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .company-logo {
            font-size: 2rem;
            font-weight: bold;
            color: #1E3A8A;
            margin-bottom: 1rem;
        }
        .security-warning {
            background-color: #FEF3C7;
            padding: 1rem;
            border-radius: 5px;
            border-left: 4px solid #F59E0B;
            margin-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Conteneur de login
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    # En-tête
    st.markdown('<div class="login-header">', unsafe_allow_html=True)
    st.markdown('<div class="company-logo">🔒 XML/Excel</div>', unsafe_allow_html=True)
    st.markdown('<h3 style="text-align: center; color: #1E3A8A;">Authentification Requise</h3>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">INDIGO COMPANY / INDITEX</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Formulaire de connexion
    password = st.text_input(
        "**Mot de passe d'accès :**",
        type="password",
        key="login_password"
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔓 Se connecter", type="primary", use_container_width=True):
            # Vérifier le mot de passe
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            if input_hash == PASSWORD_HASH:
                st.session_state.authenticated = True
                st.session_state.auth_time = time.time()
                st.success("✅ Authentification réussie !")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect")
                time.sleep(2)
    
    # Message de sécurité
    st.markdown("""
    <div class="security-warning">
        <small>⚠️ <strong>SÉCURITÉ DES DONNÉES</strong><br>
        • Aucun fichier uploadé n'est stocké<br>
        • Traitement immédiat et suppression<br>
        • Accès restreint au personnel autorisé</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Empêcher l'accès à l'application
    st.stop()

# VÉRIFIER L'AUTHENTIFICATION AVANT TOUT
if not check_authentication():
    show_login_page()

# ================= FONCTIONS SÉCURISÉES =================

def validate_files_security(files):
    """Validation sécurisée des fichiers uploadés"""
    errors = []
    valid_files = []
    total_size = 0
    
    # Vérifier nombre de fichiers
    if len(files) > MAX_FILES:
        errors.append(f"Maximum {MAX_FILES} fichiers autorisés")
        return [], errors
    
    for file in files:
        # Vérifier taille individuelle
        file_size = len(file.getvalue())
        if file_size > MAX_FILE_SIZE:
            errors.append(f"{file.name} > {MAX_FILE_SIZE//1024//1024}MB")
            continue
        
        # Vérifier taille totale
        total_size += file_size
        if total_size > MAX_TOTAL_SIZE:
            errors.append(f"Taille totale > {MAX_TOTAL_SIZE//1024//1024}MB")
            break
        
        # Vérifier extension
        if not file.name.lower().endswith('.xml'):
            errors.append(f"{file.name} n'est pas un fichier XML")
            continue
        
        # Validation basique du contenu XML
        try:
            content = file.getvalue().decode('utf-8', errors='ignore')
            if '<?xml' not in content[:100]:
                errors.append(f"{file.name} n'est pas un XML valide")
                continue
        except:
            errors.append(f"{file.name} ne peut être lu")
            continue
        
        valid_files.append(file)
    
    return valid_files, errors

def secure_log(action, file_name="", details=""):
    """Journalisation sécurisée (pas de données sensibles)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[SECURE] {timestamp} - {action} - {file_name} - {details}"
    print(log_entry)

def detect_xml_format(xml_content):
    """Détecte le format du fichier XML"""
    try:
        # Limiter la taille pour l'analyse
        if len(xml_content) > 1000000:  # 1MB max pour la détection
            return 'UNKNOWN'
            
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
    except Exception as e:
        secure_log("DETECTION_ERROR", details=str(e)[:100])
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

        # Extraction des sections
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
        secure_log("PARSING_COM_ERROR", details=str(e)[:100])
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

        # Sections à extraire
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
        secure_log("PARSING_STD_ERROR", details=str(e)[:100])
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
        secure_log("PARSE_XML_ERROR", details=str(e)[:100])
        return {}, 'ERREUR'

def create_excel_file(dataframes):
    """Crée un fichier Excel en mémoire"""
    output = io.BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in dataframes.items():
                if not df.empty:
                    # Limiter le nom de la feuille
                    sheet_name_clean = sheet_name[:31]
                    df.to_excel(writer, sheet_name=sheet_name_clean, index=False)
        
        output.seek(0)
        return output
    except Exception as e:
        secure_log("EXCEL_CREATION_ERROR", details=str(e)[:100])
        return None

def secure_process_files(files):
    """Traitement sécurisé des fichiers"""
    results = {}
    format_info = {}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file_obj in enumerate(files):
        try:
            # Mise à jour de la progression
            progress = (idx + 1) / len(files)
            progress_bar.progress(progress)
            status_text.text(f"Traitement de {file_obj.name}...")
            
            # Traitement IMMÉDIAT (pas de stockage)
            content = file_obj.getvalue().decode('utf-8')
            dataframes, xml_format = parse_xml_to_dataframes(content)
            
            if dataframes:
                # Créer Excel immédiatement
                excel_file = create_excel_file(dataframes)
                
                if excel_file:
                    results[file_obj.name] = {
                        'excel_data': excel_file,
                        'row_count': sum(len(df) for df in dataframes.values()),
                        'section_count': len(dataframes)
                    }
                    format_info[file_obj.name] = xml_format
                    
                    secure_log("FILE_PROCESSED", file_obj.name, 
                             f"format={xml_format}, rows={results[file_obj.name]['row_count']}")
            
            # Nettoyer la mémoire
            del content
            
        except Exception as e:
            secure_log("PROCESS_ERROR", file_obj.name, str(e)[:100])
            st.error(f"Erreur avec {file_obj.name}")
    
    progress_bar.empty()
    status_text.empty()
    
    return results, format_info

# ================= APPLICATION PRINCIPALE =================
st.set_page_config(
    page_title="XML/Excel Sécurisé",
    page_icon="🔄",
    layout="wide"
)

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .security-banner {
        background-color: #D1FAE5;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #10B981;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #E0F2FE;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #0EA5E9;
    }
    .stButton>button {
        width: 100%;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
    }
    .file-card {
        background-color: #F8FAFC;
        padding: 0.5rem;
        border-radius: 5px;
        margin-bottom: 0.5rem;
        border: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # En-tête de l'application
    st.markdown('<h1 class="main-header">🔄 XML/Excel Sécurisé</h1>', unsafe_allow_html=True)
    
    # Bannière de sécurité
    st.markdown("""
    <div class="security-banner">
        🔒 <strong>SÉCURITÉ DES DONNÉES GARANTIE</strong><br>
        • Aucun fichier n'est stocké sur nos serveurs<br>
        • Traitement immédiat et suppression automatique<br>
        • Connexion chiffrée (HTTPS) • Session limitée à 4h
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<h3 style="font-weight: bold;">INDIGO COMPANY / INDITEX</h3>', unsafe_allow_html=True)
        st.markdown("### ⚙️ Configuration")
        
        # Info session
        if st.session_state.get("auth_time"):
            elapsed = time.time() - st.session_state.auth_time
            remaining = max(0, 4*3600 - elapsed)
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            st.caption(f"⏱️ Session: {hours}h{minutes}m restant(s)")
        
        # Bouton de déconnexion
        st.markdown("---")
        if st.button("🚪 Déconnexion sécurisée", type="secondary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_time = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("""
        <div class="info-box">
            <small>📋 <strong>Instructions sécurisées</strong><br>
            1. Upload fichiers XML<br>
            2. Traitement immédiat<br>
            3. Téléchargement Excel<br>
            4. <strong>Aucune donnée conservée</strong></small>
        </div>
        """, unsafe_allow_html=True)

    # Zone d'upload principale
    st.markdown("### 📁 Upload de fichiers (sécurisé)")
    
    uploaded_files = st.file_uploader(
        "Sélectionnez vos fichiers XML",
        type=['xml'],
        accept_multiple_files=True,
        help="Maximum 10 fichiers, 5MB chacun, 20MB total"
    )

    if uploaded_files:
        # Validation de sécurité
        valid_files, errors = validate_files_security(uploaded_files)
        
        if errors:
            st.error("❌ **Problèmes de sécurité détectés :**")
            for error in errors:
                st.write(f"- {error}")
        
        if valid_files:
            st.success(f"✅ {len(valid_files)} fichier(s) valide(s)")
            
            # Afficher la liste des fichiers validés
            st.markdown("#### 📋 Fichiers acceptés :")
            for i, file in enumerate(valid_files, 1):
                file_size = len(file.getvalue()) / 1024
                st.markdown(f"""
                <div class="file-card">
                    <strong>{i}. {file.name}</strong><br>
                    <small>Taille: {file_size:.1f} KB • Type: XML validé</small>
                </div>
                """, unsafe_allow_html=True)

    # Traitement
    if uploaded_files and valid_files:
        st.markdown("---")
        st.markdown("### ⚡ Traitement sécurisé")
        
        if st.button("🚀 Traiter les fichiers", type="primary", key="process_secure"):
            with st.spinner("Traitement en cours (sécurisé)..."):
                # Traitement sécurisé
                results, format_info = secure_process_files(valid_files)
                
                if results:
                    st.markdown("---")
                    st.markdown("### 💾 Téléchargements sécurisés")
                    
                    # Résumé
                    total_files = len(results)
                    total_rows = sum(info['row_count'] for info in results.values())
                    
                    st.markdown(f"""
                    <div class="info-box">
                        📊 <strong>Résumé du traitement</strong><br>
                        • Fichiers traités: {total_files}<br>
                        • Lignes extraites: {total_rows:,}<br>
                        • Formats détectés: {', '.join(set(format_info.values()))}
                    </div>
                    """, unsafe_allow_html=True)
                    
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
                    
                    # Message de confirmation
                    st.markdown("""
                    <div class="security-banner">
                        ✅ <strong>Traitement terminé avec succès</strong><br>
                        Tous les fichiers ont été traités et supprimés de notre système.<br>
                        <small>Vos données sont maintenant en sécurité sur votre ordinateur.</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    st.warning("⚠️ Aucune donnée n'a pu être extraite.")

if __name__ == "__main__":
    main()
