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

# Fonction de parsing par lots
def parse_xml_in_chunks(xml_content, chunk_size=200):
    """
    Parse un fichier XML ItxCloseExport par lots de TICKETS.
    Génère des dictionnaires de DataFrames pour chaque lot.
    
    Args:
        xml_content (str): Contenu du fichier XML
        chunk_size (int): Nombre de tickets à traiter par lot
    
    Yields:
        tuple: (numéro_du_lot, total_tickets, dictionnaire_de_dataframes)
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        st.error(f"❌ Erreur de parsing XML : {e}")
        return
    
    # Récupérer les infos de l'en-tête (une seule fois)
    store_info = {}
    store_info_elem = root.find('STORE_INFO')
    if store_info_elem is not None:
        for child in store_info_elem:
            if child.text:
                store_info[child.tag] = child.text
            else:
                store_info[child.tag] = ""
    
    all_tickets = root.findall('.//TICKET')
    total_tickets = len(all_tickets)
    
    for i in range(0, total_tickets, chunk_size):
        chunk_tickets = all_tickets[i:i+chunk_size]
        
        # DataFrames pour ce lot
        tickets_data = []
        lines_data = []
        ticket_counters_data = []
        ticket_auths_data = []
        
        for ticket_elem in chunk_tickets:
            try:
                # --- Extraction des attributs du ticket ---
                ticket_dict = dict(ticket_elem.attrib)
                
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
                
                # --- Extraction des lignes de vente (SALE_LINES) ---
                for line_elem in ticket_elem.findall('.//LINE'):
                    line_dict = dict(line_elem.attrib)
                    
                    # Ajouter les clés du ticket pour faire la jointure
                    line_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                    line_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                    line_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                    line_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                    
                    # Extraire les champs de la ligne
                    line_fields = ['serial', 'date', 'time', 'lineNumber', 'barcode', 
                                  'campaignYear', 'campaign', 'description', 'familyCode', 
                                  'subFamilyCode', 'period', 'departmentId', 'quantity', 
                                  'orgPrice', 'price', 'employeeId', 'isVoidLine', 
                                  'operationTypeGroup', 'lineType', 'controlCode', 'productTypeId']
                    
                    for field in line_fields:
                        sub_elem = line_elem.find(field)
                        if sub_elem is not None and sub_elem.text:
                            line_dict[field] = sub_elem.text.strip()
                        else:
                            line_dict[field] = ""
                    
                    # Extraire les taxes
                    tax_list = []
                    for tax_elem in line_elem.findall('.//LINE_TAX'):
                        tax_info = {
                            'taxPercent': tax_elem.findtext('taxPercent', ''),
                            'idTaxRule': tax_elem.findtext('idTaxRule', '')
                        }
                        if tax_info['taxPercent'] or tax_info['idTaxRule']:
                            tax_list.append(f"{tax_info['taxPercent']}%")
                    
                    line_dict['taxes'] = '|'.join(tax_list) if tax_list else ""
                    
                    # Extraire les promotions
                    promo_list = []
                    for promo_elem in line_elem.findall('.//PROMOTION'):
                        promo_name = promo_elem.findtext('name', '')
                        if promo_name:
                            promo_list.append(promo_name)
                    
                    line_dict['promotions'] = '|'.join(promo_list) if promo_list else ""
                    
                    lines_data.append(line_dict)
                
                # --- Extraction des TICKET_COUNTER_LIST ---
                for counter_list_elem in ticket_elem.findall('.//TICKET_COUNTER_LIST/TICKET_COUNTER'):
                    counter_dict = dict(counter_list_elem.attrib)
                    counter_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                    counter_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                    counter_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                    counter_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                    ticket_counters_data.append(counter_dict)
                
                # --- Extraction des TICKET_AUTH_LIST ---
                for auth_elem in ticket_elem.findall('.//TICKET_AUTH_LIST/TICKET_AUTH'):
                    auth_dict = {}
                    for child in auth_elem:
                        auth_dict[child.tag] = child.text if child.text else ""
                    
                    auth_dict['TICKET_STOREID'] = ticket_elem.attrib.get('STOREID', '')
                    auth_dict['TICKET_POSNUMBER'] = ticket_elem.attrib.get('POSNUMBER', '')
                    auth_dict['TICKET_OPERATIONNUMBER'] = ticket_elem.attrib.get('OPERATIONNUMBER', '')
                    auth_dict['TICKET_TICKETNUMBER'] = ticket_elem.attrib.get('TICKETNUMBER', '')
                    ticket_auths_data.append(auth_dict)
            
            except Exception as e:
                st.warning(f"⚠️ Erreur sur un ticket dans le lot {i//chunk_size + 1}: {str(e)[:100]}")
                continue
        
        # Créer les DataFrames pour ce lot
        chunk_dfs = {}
        
        if tickets_data:
            chunk_dfs['TICKETS'] = pd.DataFrame(tickets_data)
        
        if lines_data:
            chunk_dfs['SALE_LINES'] = pd.DataFrame(lines_data)
        
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
    
    Args:
        dataframes_dict (dict): Dictionnaire {nom_feuille: dataframe}
    
    Returns:
        BytesIO: Fichier Excel en mémoire, ou None si erreur
    """
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in dataframes_dict.items():
                if not df.empty:
                    # Limiter le nom de la feuille à 31 caractères (limite Excel)
                    safe_sheet_name = sheet_name[:31]
                    df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
                    
                    # Ajuster la largeur des colonnes
                    worksheet = writer.sheets[safe_sheet_name]
                    for column in df:
                        column_length = max(df[column].astype(str).map(len).max(), len(str(column)))
                        column_length = min(column_length, 50)  # Max 50 caractères
                        col_idx = df.columns.get_loc(column)
                        worksheet.column_dimensions[chr(65 + col_idx)].width = column_length + 2
        
        output.seek(0)
        return output
    
    except Exception as e:
        st.error(f"❌ Erreur lors de la création du fichier Excel : {str(e)}")
        return None

# Initialisation de la session
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Interface principale
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown("### 📊 Statistiques")
    st.info("""
    **Capacités :**
    * Max 20 fichiers
    * Max 50MB par fichier
    * Traitement par lots
    * Fichiers Excel multiples
    """)

with col2:
    st.markdown("### 📁 Upload de fichiers")
    
    uploaded_files = st.file_uploader(
        "Sélectionnez vos fichiers XML",
        type=['xml'],
        accept_multiple_files=True,
        help="Vous pouvez sélectionner plusieurs fichiers XML ItxCloseExport"
    )
    
    if uploaded_files:
        # Validation des fichiers
        valid_files, large_files = validate_files(uploaded_files)
        
        if valid_files:
            # Afficher les fichiers avec leurs tailles
            st.markdown(f"#### ✅ {len(valid_files)} fichier(s) XML prêt(s) au traitement")
            
            for file in valid_files:
                file_size_mb = len(file.getvalue()) / (1024 * 1024)
                file_size_display = f"{file_size_mb:.1f} MB"
                if file_size_mb > 30:
                    file_size_display += " ⚠️"
                
                st.markdown(f"""
                <div class="file-info">
                    <strong>{file.name}</strong><br>
                    <small>Taille: {file_size_display}</small>
                </div>
                """, unsafe_allow_html=True)
            
            # Avertissement pour fichiers très gros
            if large_files:
                st.markdown("""
                <div class="warning-box">
                    ⚠️ <strong>Fichiers volumineux détectés</strong><br>
                    <small>Les fichiers de plus de 30MB seront traités par lots pour éviter les problèmes de mémoire.</small>
                </div>
                """, unsafe_allow_html=True)
                
                for large_file in large_files:
                    st.caption(f"• {large_file}")
            
            # Sélecteur de taille de lot
            chunk_size = st.slider(
                "📊 Taille des lots (nombre de tickets par fichier Excel)",
                min_value=50,
                max_value=500,
                value=200,
                step=50,
                help="Plus le lot est petit, plus il y aura de fichiers Excel, mais le traitement sera plus stable"
            )
            
            # Bouton de traitement
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            with col_btn2:
                if st.button("🚀 Démarrer le traitement", type="primary", use_container_width=True):
                    results = {}
                    failed_files = []
                    
                    # Barre de progression principale
                    main_progress = st.progress(0)
                    status_text = st.empty()
                    
                    for file_idx, file_obj in enumerate(valid_files):
                        try:
                            status_text.text(f"📖 Lecture de {file_obj.name}...")
                            content = file_obj.getvalue().decode('utf-8', errors='ignore')
                            
                            file_results = []
                            chunk_count = 0
                            
                            # Traitement par lots
                            for chunk_num, total_tickets, chunk_dfs in parse_xml_in_chunks(content, chunk_size):
                                chunk_count += 1
                                
                                # Mise à jour de la progression
                                progress = (file_idx + chunk_num / max(1, math.ceil(total_tickets/chunk_size))) / len(valid_files)
                                main_progress.progress(min(progress, 1.0))
                                
                                status_text.text(f"🔄 Traitement de {file_obj.name} - Lot {chunk_num}/{math.ceil(total_tickets/chunk_size)}...")
                                
                                if chunk_dfs:
                                    excel_file = create_excel_file(chunk_dfs)
                                    
                                    if excel_file:
                                        file_results.append({
                                            'chunk_num': chunk_num,
                                            'excel_data': excel_file,
                                            'row_count': sum(len(df) for df in chunk_dfs.values() if isinstance(df, pd.DataFrame) and not df.empty),
                                            'sections': list(chunk_dfs.keys())
                                        })
                                    else:
                                        failed_files.append(f"{file_obj.name} (lot {chunk_num} - erreur Excel)")
                            
                            if file_results:
                                results[file_obj.name] = file_results
                                status_text.text(f"✅ {file_obj.name} traité avec succès - {len(file_results)} lots")
                            else:
                                failed_files.append(f"{file_obj.name} (aucune donnée extraite)")
                        
                        except Exception as e:
                            failed_files.append(f"{file_obj.name} (erreur: {str(e)[:100]})")
                            continue
                    
                    # Nettoyage
                    main_progress.empty()
                    status_text.empty()
                    
                    # Affichage des résultats
                    if results:
                        st.markdown("---")
                        st.markdown("### ✅ Traitement terminé")
                        
                        # Statistiques
                        total_files = len(results)
                        total_chunks = sum(len(chunks) for chunks in results.values())
                        total_rows = sum(
                            chunk['row_count'] 
                            for chunks in results.values() 
                            for chunk in chunks
                        )
                        
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            st.metric("Fichiers XML", total_files)
                        with col_stat2:
                            st.metric("Fichiers Excel", total_chunks)
                        with col_stat3:
                            st.metric("Lignes totales", f"{total_rows:,}")
                        with col_stat4:
                            st.metric("Taille de lot", f"{chunk_size} tickets")
                        
                        # Avertissement pour échecs
                        if failed_files:
                            st.warning(f"⚠️ {len(failed_files)} lot(s) ont rencontré des erreurs")
                            with st.expander("Voir les détails des erreurs"):
                                for failed in failed_files[:10]:
                                    st.write(f"• {failed}")
                                if len(failed_files) > 10:
                                    st.write(f"... et {len(failed_files)-10} autres")
                        
                        st.markdown("---")
                        st.markdown("### 💾 Téléchargements")
                        
                        # Téléchargements organisés par fichier source
                        for file_name, chunks_info in results.items():
                            base_name = os.path.splitext(file_name)[0]
                            
                            with st.expander(f"📁 {file_name} - {len(chunks_info)} lots"):
                                # Statistiques du fichier
                                file_total_rows = sum(c['row_count'] for c in chunks_info)
                                st.caption(f"Total lignes: {file_total_rows:,} | Sections: {', '.join(set().union(*[c['sections'] for c in chunks_info]))}")
                                
                                # Boutons de téléchargement en grille
                                cols = st.columns(4)
                                for i, chunk_info in enumerate(chunks_info):
                                    with cols[i % 4]:
                                        chunk_label = f"Lot {chunk_info['chunk_num']}"
                                        if 'row_count' in chunk_info:
                                            chunk_label += f" ({chunk_info['row_count']} lignes)"
                                        
                                        st.download_button(
                                            label=chunk_label,
                                            data=chunk_info['excel_data'],
                                            file_name=f"{base_name}_part{chunk_info['chunk_num']:03d}.xlsx",
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            key=f"dl_{hashlib.md5(f'{file_name}_{chunk_info["chunk_num"]}'.encode()).hexdigest()[:8]}",
                                            use_container_width=True
                                        )
                            
                            st.divider()
                        
                        # Bouton pour tout télécharger (simulé - redirige vers les téléchargements individuels)
                        st.info("💡 Cliquez sur chaque lot pour télécharger les fichiers Excel individuellement")
                        
                        # Effet visuel de succès
                        st.balloons()
                        st.success("🎉 Tous les lots disponibles ont été traités avec succès !")
                        
                    else:
                        st.error("❌ Aucun fichier n'a pu être traité")
                        if failed_files:
                            with st.expander("Détails des erreurs"):
                                for failed in failed_files[:20]:
                                    st.write(f"• {failed}")
        else:
            st.info("📝 Veuillez sélectionner des fichiers XML valides")

with col3:
    st.markdown("### ℹ️ Aide")
    
    with st.expander("Comment utiliser ?"):
        st.markdown("""
        1. **Sélectionnez** vos fichiers XML ItxCloseExport
        2. **Ajustez** la taille des lots (optionnel)
        3. **Cliquez** sur "Démarrer le traitement"
        4. **Téléchargez** les fichiers Excel générés
        
        **Fonctionnalités :**
        * Traitement par lots pour éviter les problèmes de mémoire
        * Plusieurs feuilles Excel structurées
        * Gestion des gros fichiers (>100MB)
        * Indicateurs de progression
        """)
    
    with st.expander("Structure des fichiers Excel"):
        st.markdown("""
        **Feuilles générées :**
        * `STORE_INFO` : Informations générales du magasin
        * `TICKETS` : Entêtes des tickets de caisse
        * `SALE_LINES` : Lignes de vente détaillées
        * `TICKET_COUNTERS` : Compteurs associés
        * `TICKET_AUTHS` : Autorisations spéciales
        """)
    
    with st.expander("Dépannage"):
        st.markdown("""
        **Problèmes courants :**
        
        * **Fichier trop gros** : Réduisez la taille des lots
        * **Erreur mémoire** : Utilisez des lots plus petits (50-100)
        * **Fichier vide** : Vérifiez le format XML
        * **Timeout** : Traitez moins de fichiers à la fois
        """)
    
    with st.expander("Contact"):
        st.markdown("""
        **Support technique**
        
        En cas de problème persistant :
        * Vérifiez que vos fichiers sont bien au format ItxCloseExport
        * Réduisez le nombre de fichiers traités simultanément
        * Consultez les logs d'erreur
        """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <small>Convertisseur XML ItxCloseExport v2.0 - Traitement par lots pour fichiers volumineux</small>
    </div>
    """,
    unsafe_allow_html=True
)
