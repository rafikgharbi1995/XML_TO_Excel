import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import hashlib
import time
import gc

# ================= CONFIGURATION SÉCURITÉ =================
APP_PASSWORD = "Indigo2025**"
PASSWORD_HASH = hashlib.sha256(APP_PASSWORD.encode()).hexdigest()

def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

def show_login_page():
    st.set_page_config(page_title="Authentification", page_icon="🔒", layout="centered")
    st.markdown('<h3 style="text-align: center;">Authentification INDIGO</h3>', unsafe_allow_html=True)
    password = st.text_input("Mot de passe :", type="password")
    if st.button("Se connecter", type="primary", use_container_width=True):
        if hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect")
    st.stop()

if not check_authentication():
    show_login_page()

# ================= FONCTION DE TRANSFORMATION =================

def parse_xml_to_sheets(file_obj):
    """Extraction automatique de toutes les balises du XML vers Excel"""
    try:
        file_obj.seek(0)
        # Utilisation de parse() pour économiser la mémoire sur les fichiers de 12MB+
        tree = ET.parse(file_obj)
        root = tree.getroot()
        
        dataframes = {}

        # Liste des sections à chercher
        sections_map = {
            'VENTES': ['.//LINE', './/ITEM', './/SALE_LINE'],
            'TICKETS_RECAP': ['.//TICKET', './/VALID_TICKET'],
            'PAIEMENTS': ['.//MEDIA', './/PAYMENT'],
            'TRANSACTIONS': ['.//TRANSACTION'],
            'MAGASIN': ['.//STORE_INFO']
        }

        for sheet_name, xpaths in sections_map.items():
            rows = []
            for xpath in xpaths:
                for elem in root.findall(xpath):
                    # Extraction de TOUTES les données de la balise
                    row = {}
                    # 1. Attributs
                    row.update(elem.attrib)
                    # 2. Sous-balises
                    for child in elem:
                        if len(child) == 0:
                            row[child.tag] = child.text
                        else:
                            # Pour les balises imbriquées (taxes, etc.)
                            for sub in child:
                                row[f"{child.tag}_{sub.tag}"] = sub.text
                    rows.append(row)
            
            if rows:
                df = pd.DataFrame(rows)
                
                # NETTOYAGE SÉCURISÉ DES NOMBRES (Correction de l'erreur .str)
                for col in df.columns:
                    # On ne transforme en nombre que si la colonne contient du texte
                    if df[col].dtype == 'object':
                        # Remplacement des virgules par des points pour Excel
                        temp_col = df[col].astype(str).str.replace(',', '.')
                        # Conversion en nombre si possible, sinon garde le texte
                        df[col] = pd.to_numeric(temp_col, errors='ignore')
                
                dataframes[sheet_name] = df

        # Libération mémoire
        del root
        del tree
        gc.collect()
        
        return dataframes
    except Exception as e:
        st.error(f"Erreur lors de la lecture du XML : {e}")
        return None

def create_excel(dataframes):
    output = io.BytesIO()
    try:
        # Utilisation de xlsxwriter pour la performance
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in dataframes.items():
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"Erreur Excel : {e}")
        return None

# ================= INTERFACE =================

st.set_page_config(page_title="XML to Excel PRO", layout="wide")
st.title("🔄 Convertisseur XML Automatique")
st.write("Format compatible : ItxCloseExport (Standard & COM)")

uploaded_files = st.file_uploader("Charger vos fichiers XML", type=['xml'], accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Convertir les fichiers", type="primary", use_container_width=True):
        for file in uploaded_files:
            with st.status(f"Analyse de {file.name}...", expanded=True) as status:
                
                dfs = parse_xml_to_sheets(file)
                
                if dfs:
                    excel_data = create_excel(dfs)
                    if excel_data:
                        status.update(label=f"✅ {file.name} converti", state="complete")
                        st.download_button(
                            label=f"📥 Télécharger {file.name}.xlsx",
                            data=excel_data,
                            file_name=f"{file.name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"btn_{file.name}"
                        )
                    
                    # Nettoyage mémoire immédiat
                    del dfs
                    del excel_data
                    gc.collect()
                else:
                    status.update(label=f"❌ Échec de lecture pour {file.name}", state="error")
