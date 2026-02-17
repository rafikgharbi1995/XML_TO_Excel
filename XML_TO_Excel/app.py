import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import hashlib
import time
import gc
import os

# ================= CONFIGURATION SÉCURITÉ =================
APP_PASSWORD = "Indigo2025**"
PASSWORD_HASH = hashlib.sha256(APP_PASSWORD.encode()).hexdigest()

# ================= SYSTÈME D'AUTHENTIFICATION =================
def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.auth_time = None
    
    if st.session_state.authenticated and st.session_state.auth_time:
        if time.time() - st.session_state.auth_time < 4 * 3600: # 4 heures
            return True
    return False

def show_login_page():
    st.set_page_config(page_title="Connexion Indigo", page_icon="🔒", layout="centered")
    st.markdown("""
        <style>
        .login-box { padding: 2rem; border-radius: 10px; border: 1px solid #ddd; background: #f9f9f9; }
        </style>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.title("🔒 Accès Sécurisé")
        st.write("Convertisseur XML vers Excel - INDIGO COMPANY")
        password = st.text_input("Mot de passe :", type="password")
        if st.button("Se connecter", use_container_width=True):
            if hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH:
                st.session_state.authenticated = True
                st.session_state.auth_time = time.time()
                st.rerun()
            else:
                st.error("Mot de passe incorrect")
    st.stop()

# ================= MOTEUR DE TRAITEMENT OPTIMISÉ =================

def parse_xml_smart(file_obj):
    """Analyse le XML en mode mémoire optimisé"""
    try:
        # On utilise ET.parse(file) au lieu de ET.fromstring(content)
        # Cela permet de lire le fichier sans charger le texte brut en RAM
        file_obj.seek(0)
        tree = ET.parse(file_obj)
        root = tree.getroot()
        root_tag = root.tag
        
        dataframes = {}

        # 1. Détecter si c'est le format ITX_COM ou STANDARD
        is_com = 'ITX_CLOSE_EXPORT_COM' in root_tag or root.find('.//SALE_LINE_ITEMS') is not None
        
        if is_com:
            # --- FORMAT ITX_COM ---
            sections = [
                ('VALID_TICKETS', 'TICKET'),
                ('SALE_LINE_ITEMS', 'ITEM'),
                ('MEDIA_LINES', 'MEDIA'),
                ('CUSTOMER_TICKETS', 'CT_TICKET')
            ]
            for sec_name, elem_name in sections:
                container = root.find(f'.//{sec_name}')
                if container is not None:
                    rows = []
                    for item in container.findall(elem_name):
                        row = {child.tag: child.text for child in item}
                        rows.append(row)
                    if rows:
                        dataframes[sec_name] = pd.DataFrame(rows)
        else:
            # --- FORMAT STANDARD ---
            config = [
                ('.//SALE_LINES/LINE', 'SALE_LINES', ['STOREID', 'POSNUMBER', 'TICKETNUMBER'], 
                 ['barcode', 'description', 'quantity', 'price', 'orgPrice', 'date', 'familyCode', 'lineType']),
                ('.//VALID_TICKETS/TICKET', 'VALID_TICKETS', ['STOREID', 'POSNUMBER', 'TICKETNUMBER'], 
                 ['date', 'time', 'totalSale', 'totalNet', 'operatorId', 'isVoidTicket']),
                ('.//MEDIA_LINES/MEDIA', 'MEDIA_LINES', ['STOREID', 'TICKETNUMBER'], 
                 ['date', 'paid', 'paymentMethod']),
                ('.//TRANSACTIONS/TRANSACTION', 'TRANSACTIONS', None, 
                 ['code', 'description', 'debit', 'credit', 'txType'])
            ]
            
            for xpath, sheet_name, attrs, fields in config:
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

        # Extraction des infos Magasin (STORE_INFO)
        store_info = root.find('.//STORE_INFO')
        if store_info is not None:
            dataframes['MAGASIN'] = pd.DataFrame([{c.tag: c.text for c in store_info}])

        # Libération immédiate de la mémoire XML
        del tree
        del root
        gc.collect()
        
        return dataframes
    except Exception as e:
        st.error(f"Erreur lors de l'analyse : {e}")
        return None

def create_excel(dataframes):
    """Génère le fichier Excel avec xlsxwriter (très économe en RAM)"""
    output = io.BytesIO()
    try:
        # xlsxwriter est beaucoup plus performant que openpyxl pour les gros volumes
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in dataframes.items():
                if not df.empty:
                    # On nettoie le nom de la feuille (max 31 car)
                    clean_name = sheet_name[:31].replace('[','').replace(']','')
                    df.to_excel(writer, sheet_name=clean_name, index=False)
        
        output.seek(0)
        return output
    except Exception as e:
        st.error(f"Erreur lors de la création Excel : {e}")
        return None

# ================= INTERFACE PRINCIPALE =================

if not check_authentication():
    show_login_page()

st.set_page_config(page_title="XML Converter PRO", page_icon="🔄", layout="wide")

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/209/209110.png", width=100)
    st.title("Menu")
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    st.write("**Statut :** Connecté")
    st.write("**Mode :** Haute Performance (Large Files)")

# Page principale
st.title("🔄 Convertisseur XML vers Excel")
st.info("Ce mode est optimisé pour les fichiers volumineux (jusqu'à 100 Mo).")

files = st.file_uploader("Glissez vos fichiers XML ici", type=['xml'], accept_multiple_files=True)

if files:
    st.write(f"📂 **{len(files)}** fichier(s) sélectionné(s)")
    
    if st.button("🚀 Lancer la conversion", type="primary", use_container_width=True):
        for file in files:
            with st.status(f"Traitement de {file.name}...", expanded=True) as status:
                
                # Étape 1 : Lecture
                start_time = time.time()
                dfs = parse_xml_smart(file)
                
                if dfs:
                    # Étape 2 : Conversion Excel
                    excel_data = create_excel(dfs)
                    
                    if excel_data:
                        elapsed = time.time() - start_time
                        status.update(label=f"✅ {file.name} converti en {elapsed:.1f}s", state="complete")
                        
                        st.download_button(
                            label=f"📥 Télécharger {file.name}.xlsx",
                            data=excel_data,
                            file_name=f"{file.name.replace('.xml', '')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{file.name}"
                        )
                    
                    # Nettoyage mémoire pour le fichier suivant
                    del dfs
                    del excel_data
                    gc.collect()
                else:
                    status.update(label=f"❌ Erreur sur {file.name}", state="error")

st.markdown("---")
st.caption("Indigo Company - Optimisation Performance 2025")
