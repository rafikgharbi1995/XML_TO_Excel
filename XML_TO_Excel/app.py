import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os
import io
import hashlib
import time
import gc  # Pour la gestion de la mémoire

# ================= CONFIGURATION SÉCURITÉ =================
APP_PASSWORD = "Indigo2025**"
PASSWORD_HASH = hashlib.sha256(APP_PASSWORD.encode()).hexdigest()

# LIMITES
MAX_FILES = 20
# Streamlit a sa propre limite (souvent 200MB par défaut), on reste cohérent
# ==========================================================

def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.auth_time = None
    if st.session_state.authenticated and st.session_state.auth_time:
        if time.time() - st.session_state.auth_time < 4 * 3600:
            return True
    return False

def show_login_page():
    st.set_page_config(page_title="Authentification", page_icon="🔒")
    st.markdown('<h3 style="text-align: center;">Authentification INDIGO</h3>', unsafe_allow_html=True)
    password = st.text_input("Mot de passe :", type="password")
    if st.button("Se connecter"):
        if hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.session_state.auth_time = time.time()
            st.rerun()
        else:
            st.error("Mot de passe incorrect")
    st.stop()

if not check_authentication():
    show_login_page()

# ================= FONCTIONS OPTIMISÉES =================

def get_xml_root_efficiently(file_obj):
    """Détermine le format sans charger tout le fichier en mémoire"""
    try:
        file_obj.seek(0)
        # On ne lit que le début du fichier pour détecter le tag racine
        context = ET.iterparse(file_obj, events=('start',))
        _, elem = next(context)
        root_tag = elem.tag
        return root_tag
    except:
        return "UNKNOWN"
    finally:
        file_obj.seek(0)

def parse_xml_optimized(file_obj):
    """Analyse le XML de manière plus efficace pour la mémoire"""
    try:
        file_obj.seek(0)
        tree = ET.parse(file_obj)
        root = tree.getroot()
        root_tag = root.tag
        
        dataframes = {}

        # Détection du format
        is_com = 'ITX_CLOSE_EXPORT_COM' in root_tag or root.find('.//SALE_LINE_ITEMS') is not None
        
        if is_com:
            # Format ITX_COM
            sections = [
                ('VALID_TICKETS', 'TICKET'),
                ('SALE_LINE_ITEMS', 'ITEM'),
                ('MEDIA_LINES', 'MEDIA'),
                ('CUSTOMER_TICKETS', 'CT_TICKET')
            ]
            for sec_name, elem_name in sections:
                section = root.find(f'.//{sec_name}')
                if section is not None:
                    rows = []
                    for elem in section.findall(elem_name):
                        row = {child.tag: child.text for child in elem}
                        rows.append(row)
                    if rows:
                        dataframes[sec_name] = pd.DataFrame(rows)
                        del rows # Libère la mémoire
        else:
            # Format STANDARD
            sections_config = [
                ('.//SALE_LINES/LINE', 'SALE_LINES', ['STOREID', 'POSNUMBER', 'TICKETNUMBER'], 
                 ['barcode', 'description', 'quantity', 'price', 'date', 'familyCode']),
                ('.//VALID_TICKETS/TICKET', 'VALID_TICKETS', ['STOREID', 'TICKETNUMBER'], 
                 ['date', 'time', 'totalSale', 'totalNet', 'operatorId']),
                ('.//MEDIA_LINES/MEDIA', 'MEDIA_LINES', ['STOREID', 'TICKETNUMBER'], 
                 ['date', 'paid', 'paymentMethod']),
                ('.//TRANSACTIONS/TRANSACTION', 'TRANSACTIONS', None, ['code', 'description', 'debit', 'credit'])
            ]
            
            for xpath, sheet_name, attrs, fields in sections_config:
                elements = root.findall(xpath)
                rows = []
                for elem in elements:
                    row = {}
                    if attrs:
                        for a in attrs: row[a] = elem.get(a)
                    if fields:
                        for f in fields: 
                            target = elem.find(f)
                            row[f] = target.text if target is not None else None
                    rows.append(row)
                if rows:
                    dataframes[sheet_name] = pd.DataFrame(rows)
                    del rows

        # Nettoyage explicite de l'arbre XML
        del root
        del tree
        gc.collect() 
        
        return dataframes
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
        return {}

def create_excel_optimized(dataframes):
    """Crée un Excel en utilisant xlsxwriter si possible (plus léger)"""
    output = io.BytesIO()
    try:
        # xlsxwriter est beaucoup plus rapide et économe en mémoire que openpyxl
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in dataframes.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        output.seek(0)
        return output
    except Exception as e:
        st.error(f"Erreur Excel : {e}")
        return None

# ================= INTERFACE =================
st.set_page_config(page_title="XML Converter PRO", layout="wide")
st.title("🔄 XML vers Excel (Optimisé)")

uploaded_files = st.file_uploader("Fichiers XML (Même volumineux)", type=['xml'], accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Lancer la conversion", type="primary"):
        for file in uploaded_files:
            with st.status(f"Traitement de {file.name}...", expanded=True) as status:
                start_time = time.time()
                
                # 1. Parsing
                dfs = parse_xml_optimized(file)
                
                if dfs:
                    # 2. Excel
                    excel_data = create_excel_optimized(dfs)
                    
                    if excel_data:
                        duration = time.time() - start_time
                        status.update(label=f"✅ {file.name} terminé ({duration:.1f}s)", state="complete")
                        
                        st.download_button(
                            label=f"📥 Télécharger {file.name}.xlsx",
                            data=excel_data,
                            file_name=f"{file.name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{file.name}"
                        )
                    
                    # 3. Libérer la mémoire immédiatement
                    del dfs
                    del excel_data
                    gc.collect()
                else:
                    status.update(label=f"❌ Échec sur {file.name}", state="error")
