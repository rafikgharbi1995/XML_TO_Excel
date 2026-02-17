import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
import hashlib
import os
import time
import math

# Configuration de la page
st.set_page_config(
    page_title="Convertisseur XML ItxCloseExport",
    page_icon="📊",
    layout="wide"
)

# Style CSS personnalisé
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .file-info {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .stProgress > div > div > div > div {
        background-color: #667eea;
    }
</style>
""", unsafe_allow_html=True)

# Titre principal
st.markdown("""
<div class="main-header">
    <h1>📊 Convertisseur XML ItxCloseExport → Excel</h1>
    <p>Transformez vos fichiers XML de caisse en fichiers Excel structurés</p>
</div>
""", unsafe_allow_html=True)

# INITIALISATION DE LA SESSION
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'failed_files' not in st.session_state:
    st.session_state.failed_files = []

# Fonctions de validation
def validate_files(uploaded_files):
    """Valide les fichiers uploadés"""
    valid_files = []
    large_files = []
    
    for file in uploaded_files:
        if file.name.endswith('.xml'):
            valid_files.append(file)
            file_size_mb = len(file.getvalue()) / (1024 * 1024)
            if file_size_mb > 30:
                large_files.append(file.name)
    
    return valid_files, large_files

def parse_xml_in_chunks(xml_content, chunk_size=200):
    """
    Parse un fichier XML ItxCloseExport par lots de TICKETS.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        st.error(f"❌ Erreur de parsing XML : {e}")
        return
    
    # Récupérer les infos de l'en-tête
    store_info = {}
    store_info_elem = root.find('STORE_INFO')
    if store_info_elem is not None:
        for child in store_info_elem:
            if child.text:
                store_info[child.tag] = child.text.strip()
            else:
                store_info[child.tag] = ""
    
    # Récupérer tous les tickets
    all_tickets = root.findall('.//TICKET')
    total_tickets = len(all_tickets)
    
    if total_tickets == 0:
        st.warning("⚠️ Aucun ticket trouvé dans le fichier XML")
        return
    
    for i in range(0, total_tickets, chunk_size):
        chunk_tickets = all_tickets[i:i+chunk_size]
        
        # DataFrames pour ce lot
        tickets_data = []
        lines_data = []
        ticket_counters_data = []
        ticket_auths_data = []
        ticket_data_list = []
        
        for ticket_idx, ticket_elem in enumerate(chunk_tickets):
            try:
                # --- 1. Extraction des attributs du ticket ---
                ticket_dict = {}
                for key, value in ticket_elem.attrib.items():
                    ticket_dict[key] = value
                
                # Extraire les éléments simples du ticket
                simple_fields = ['serial', 'date', 'time', 'operatorId', 'totalSale', 
                               'totalNet', 'isVoidTicket', 'employeeId', 'fiscalprinterId', 
                               'operationTypeGroup', 'roundingError']
                
                for field in simple_fields:
                    sub_elem = ticket_elem.find(field)
                    if sub_elem is not None and sub_elem.text:
                        ticket_dict[field] = sub_elem.text.strip()
                    else:
                        ticket_dict[field] = ""
                
                tickets_data.append(ticket_dict)
                
                # --- 2. Extraction des SALE_LINES ---
                # Chercher les LINE dans SALE_LINES ou directement sous TICKET
                line_elements = []
                
                # Méthode 1: Chercher dans SALE_LINES
                sale_lines = ticket_elem.find('SALE_LINES')
                if sale_lines is not None:
                    line_elements.extend(sale_lines.findall('LINE'))
                
                # Méthode 2: Chercher directement sous TICKET
                line_elements.extend(ticket_elem.findall('LINE'))
                
                for line_elem in line_elements:
                    line_dict = {}
                    
                    # Récupérer tous les attributs
                    for key, value in line_elem.attrib.items():
                        line_dict[key] = value
                    
                    # Ajouter les clés du ticket pour faire la jointure
                    line_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                    line_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                    line_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                    line_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                    
                    # Extraire tous les champs possibles de la ligne
                    line_fields = [
                        'serial', 'date', 'time', 'lineNumber', 'barcode', 
                        'campaignYear', 'campaign', 'description', 'familyCode', 
                        'subFamilyCode', 'period', 'departmentId', 'quantity', 
                        'orgPrice', 'price', 'employeeId', 'isVoidLine', 
                        'operationTypeGroup', 'lineType', 'controlCode', 'productTypeId',
                        'voidLine'
                    ]
                    
                    for field in line_fields:
                        sub_elem = line_elem.find(field)
                        if sub_elem is not None and sub_elem.text:
                            line_dict[field] = sub_elem.text.strip()
                        else:
                            line_dict[field] = ""
                    
                    # --- Extraire les taxes ---
                    tax_list = []
                    tax_list_elem = line_elem.find('LINE_TAX_LIST')
                    if tax_list_elem is not None:
                        for tax_elem in tax_list_elem.findall('LINE_TAX'):
                            tax_percent = tax_elem.findtext('taxPercent', '')
                            if tax_percent:
                                tax_list.append(f"{tax_percent}%")
                    
                    line_dict['taxes'] = '|'.join(tax_list) if tax_list else ""
                    
                    # --- Extraire les promotions ---
                    promo_list = []
                    promo_list_elem = line_elem.find('PROMOTION_LIST')
                    if promo_list_elem is not None:
                        for promo_elem in promo_list_elem.findall('PROMOTION'):
                            promo_name = promo_elem.findtext('name', '')
                            if promo_name:
                                promo_list.append(promo_name)
                    
                    line_dict['promotions'] = '|'.join(promo_list) if promo_list else ""
                    
                    lines_data.append(line_dict)
                
                # --- 3. Extraction des TICKET_DATA ---
                ticket_data_list_elem = ticket_elem.find('TICKET_DATA_LIST')
                if ticket_data_list_elem is not None:
                    for data_elem in ticket_data_list_elem.findall('TICKET_DATA'):
                        data_dict = {}
                        data_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                        data_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                        data_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                        data_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                        
                        for key, value in data_elem.attrib.items():
                            data_dict[key] = value
                        
                        if data_elem.text:
                            data_dict['value'] = data_elem.text.strip()
                        else:
                            data_dict['value'] = ""
                        
                        ticket_data_list.append(data_dict)
                
                # --- 4. Extraction des TICKET_COUNTER ---
                counter_list_elem = ticket_elem.find('TICKET_COUNTER_LIST')
                if counter_list_elem is not None:
                    for counter_elem in counter_list_elem.findall('TICKET_COUNTER'):
                        counter_dict = {}
                        counter_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                        counter_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                        counter_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                        counter_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                        
                        for key, value in counter_elem.attrib.items():
                            counter_dict[key] = value
                        
                        ticket_counters_data.append(counter_dict)
                
                # --- 5. Extraction des TICKET_AUTH ---
                auth_list_elem = ticket_elem.find('TICKET_AUTH_LIST')
                if auth_list_elem is not None:
                    for auth_elem in auth_list_elem.findall('TICKET_AUTH'):
                        auth_dict = {}
                        auth_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                        auth_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                        auth_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                        auth_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                        
                        for child in auth_elem:
                            if child.text:
                                auth_dict[child.tag] = child.text.strip()
                            else:
                                auth_dict[child.tag] = ""
                        
                        ticket_auths_data.append(auth_dict)
            
            except Exception as e:
                continue
        
        # Créer les DataFrames pour ce lot
        chunk_dfs = {}
        
        if tickets_data:
            chunk_dfs['TICKETS'] = pd.DataFrame(tickets_data)
        
        if lines_data:
            chunk_dfs['SALE_LINES'] = pd.DataFrame(lines_data)
        
        if ticket_data_list:
            chunk_dfs['TICKET_DATA'] = pd.DataFrame(ticket_data_list)
        
        if ticket_counters_data:
            chunk_dfs['TICKET_COUNTERS'] = pd.DataFrame(ticket_counters_data)
        
        if ticket_auths_data:
            chunk_dfs['TICKET_AUTHS'] = pd.DataFrame(ticket_auths_data)
        
        # Ajouter les infos d'en-tête
        if store_info:
            chunk_dfs['STORE_INFO'] = pd.DataFrame([store_info])
        
        if chunk_dfs:
            yield i // chunk_size + 1, total_tickets, chunk_dfs

def create_excel_file(dataframes_dict):
    """
    Crée un fichier Excel à partir d'un dictionnaire de DataFrames.
    """
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            sheets_created = 0
            for sheet_name, df in dataframes_dict.items():
                if not df.empty:
                    safe_sheet_name = sheet_name[:31]
                    df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
                    sheets_created += 1
                    
                    # Ajuster la largeur des colonnes
                    worksheet = writer.sheets[safe_sheet_name]
                    for idx, col in enumerate(df.columns):
                        try:
                            col_width = max(
                                df[col].astype(str).map(len).max() if not df[col].empty else 0,
                                len(str(col))
                            )
                            col_width = min(col_width + 2, 50)
                            worksheet.column_dimensions[chr(65 + idx)].width = col_width
                        except:
                            pass
            
            if sheets_created == 0:
                return None
        
        output.seek(0)
        return output
    
    except Exception as e:
        return None

# Interface principale
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown("### 📊 Statistiques")
    st.info("""
    **Capacités :**
    * Max 20 fichiers
    * Traitement par lots
    * Fichiers Excel multiples
    * Support des SALE_LINES
    """)
    
    # Afficher un résumé si des résultats existent
    if st.session_state.results:
        total_lots = sum(len(r) for r in st.session_state.results.values())
        total_tickets = sum(lot['tickets'] for r in st.session_state.results.values() for lot in r)
        total_lines = sum(lot['lines'] for r in st.session_state.results.values() for lot in r)
        
        st.markdown("### 📈 Résultats en mémoire")
        st.metric("Fichiers XML", len(st.session_state.results))
        st.metric("Fichiers Excel", total_lots)
        st.metric("Lignes de vente", f"{total_lines:,}")
        
        if st.button("🔄 Nouveau traitement", use_container_width=True):
            st.session_state.results = {}
            st.session_state.processing_complete = False
            st.session_state.failed_files = []
            st.rerun()

with col2:
    st.markdown("### 📁 Upload de fichiers")
    
    uploaded_files = st.file_uploader(
        "Sélectionnez vos fichiers XML",
        type=['xml'],
        accept_multiple_files=True,
        help="Sélectionnez vos fichiers XML ItxCloseExport"
    )
    
    if uploaded_files and not st.session_state.processing_complete:
        valid_files, large_files = validate_files(uploaded_files)
        
        if valid_files:
            st.markdown(f"#### ✅ {len(valid_files)} fichier(s) XML prêt(s)")
            
            for file in valid_files:
                file_size_mb = len(file.getvalue()) / (1024 * 1024)
                st.markdown(f"""
                <div class="file-info">
                    <strong>{file.name}</strong><br>
                    <small>Taille: {file_size_mb:.1f} MB</small>
                </div>
                """, unsafe_allow_html=True)
            
            # Sélecteur de taille de lot
            chunk_size = st.slider(
                "📊 Taille des lots (nombre de tickets par fichier Excel)",
                min_value=50,
                max_value=500,
                value=200,
                step=50
            )
            
            # Bouton de traitement
            if st.button("🚀 Démarrer le traitement", type="primary", use_container_width=True):
                # Réinitialiser les résultats précédents
                st.session_state.results = {}
                st.session_state.failed_files = []
                
                # Barre de progression
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for file_idx, file_obj in enumerate(valid_files):
                    try:
                        status_text.text(f"📖 Lecture de {file_obj.name}...")
                        content = file_obj.getvalue().decode('utf-8', errors='ignore')
                        
                        file_results = []
                        
                        # Traitement par lots
                        for chunk_num, total_tickets, chunk_dfs in parse_xml_in_chunks(content, chunk_size):
                            
                            # Mise à jour progression
                            progress = (file_idx + (chunk_num * chunk_size) / max(1, total_tickets)) / len(valid_files)
                            progress_bar.progress(min(progress, 0.99))
                            
                            status_text.text(f"🔄 Lot {chunk_num} de {file_obj.name}...")
                            
                            if chunk_dfs:
                                excel_file = create_excel_file(chunk_dfs)
                                
                                if excel_file:
                                    file_results.append({
                                        'chunk_num': chunk_num,
                                        'excel_data': excel_file,
                                        'tickets': len(chunk_dfs.get('TICKETS', pd.DataFrame())),
                                        'lines': len(chunk_dfs.get('SALE_LINES', pd.DataFrame())),
                                        'filename': file_obj.name
                                    })
                        
                        if file_results:
                            st.session_state.results[file_obj.name] = file_results
                            status_text.text(f"✅ {file_obj.name}: {len(file_results)} lots")
                        else:
                            st.session_state.failed_files.append(f"{file_obj.name} (aucune donnée)")
                    
                    except Exception as e:
                        st.session_state.failed_files.append(f"{file_obj.name} ({str(e)[:50]})")
                        continue
                
                progress_bar.empty()
                status_text.empty()
                st.session_state.processing_complete = True
                st.rerun()
    
    # AFFICHAGE DES RÉSULTATS STOCKÉS
    if st.session_state.results:
        st.markdown("---")
        st.markdown("""
        <div class="success-box">
            <strong>✅ Traitement terminé !</strong><br>
            Tous les lots sont disponibles ci-dessous. Vous pouvez télécharger chaque lot individuellement.
        </div>
        """, unsafe_allow_html=True)
        
        # Statistiques globales
        total_lots = sum(len(r) for r in st.session_state.results.values())
        total_tickets = sum(lot['tickets'] for r in st.session_state.results.values() for lot in r)
        total_lines = sum(lot['lines'] for r in st.session_state.results.values() for lot in r)
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("Fichiers XML", len(st.session_state.results))
        with col_s2:
            st.metric("Fichiers Excel", total_lots)
        with col_s3:
            st.metric("Tickets", f"{total_tickets:,}")
        with col_s4:
            st.metric("Lignes de vente", f"{total_lines:,}")
        
        st.markdown("### 💾 Téléchargements")
        
        # Afficher les lots par fichier source
        for file_name, chunks_info in st.session_state.results.items():
            base_name = os.path.splitext(file_name)[0]
            
            with st.expander(f"📁 {file_name} - {len(chunks_info)} lots", expanded=True):
                # Organiser les lots en grille
                cols = st.columns(4)
                for i, chunk_info in enumerate(chunks_info):
                    with cols[i % 4]:
                        # Créer un label descriptif
                        label = f"📊 Lot {chunk_info['chunk_num']}"
                        if chunk_info['lines'] > 0:
                            label += f"\n({chunk_info['lines']} lignes)"
                        else:
                            label += "\n(0 ligne)"
                        
                        # Bouton de téléchargement avec clé unique
                        st.download_button(
                            label=label,
                            data=chunk_info['excel_data'],
                            file_name=f"{base_name}_part{chunk_info['chunk_num']:03d}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{hashlib.md5(f'{file_name}_{chunk_info["chunk_num"]}'.encode()).hexdigest()[:8]}",
                            use_container_width=True
                        )
                
                # Ajouter une ligne de séparation
                if len(chunks_info) > 4:
                    st.markdown("<br>", unsafe_allow_html=True)
        
        # Afficher les erreurs s'il y en a
        if st.session_state.failed_files:
            with st.expander("⚠️ Fichiers en erreur"):
                for f in st.session_state.failed_files:
                    st.write(f"• {f}")
        
        # Option pour réinitialiser
        if st.button("🔄 Effacer les résultats et recommencer", use_container_width=True):
            st.session_state.results = {}
            st.session_state.processing_complete = False
            st.session_state.failed_files = []
            st.rerun()

with col3:
    st.markdown("### ℹ️ Aide")
    with st.expander("Comment utiliser ?"):
        st.markdown("""
        1. **Sélectionnez** vos fichiers XML
        2. **Ajustez** la taille des lots
        3. **Cliquez** sur Démarrer
        4. **Téléchargez** chaque lot
        
        **Important :** Les résultats restent en mémoire pendant toute la session. Vous pouvez télécharger tous les lots un par un.
        """)
    
    with st.expander("Structure des données"):
        st.markdown("""
        **Feuilles Excel :**
        * `STORE_INFO` : Infos magasin
        * `TICKETS` : Entêtes des tickets
        * **`SALE_LINES`** : Lignes de vente
        * `TICKET_DATA` : Données supplémentaires
        * `TICKET_COUNTERS` : Compteurs
        * `TICKET_AUTHS` : Autorisations
        """)
    
    with st.expander("Pourquoi plusieurs lots ?"):
        st.markdown("""
        Les gros fichiers XML sont découpés en plusieurs fichiers Excel pour :
        * Éviter les problèmes de mémoire
        * Rester sous la limite Excel (1M lignes)
        * Permettre des téléchargements plus rapides
        * Faciliter l'analyse par période
        """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'><small>Convertisseur XML ItxCloseExport v2.2 - Conservation des résultats en mémoire</small></div>",
    unsafe_allow_html=True
)
