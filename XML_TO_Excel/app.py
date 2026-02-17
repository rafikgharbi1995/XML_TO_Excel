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

# 🔐 AUTHENTIFICATION (Identique à votre code)
def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.auth_time = None
    if st.session_state.authenticated and st.session_state.auth_time:
        if time.time() - st.session_state.auth_time < 4 * 3600:
            return True
    return False

def show_login_page():
    st.set_page_config(page_title="Authentification", page_icon="🔒", layout="centered")
    st.markdown('<h3 style="text-align: center; color: #1E3A8A;">Authentification INDIGO</h3>', unsafe_allow_html=True)
    password = st.text_input("Mot de passe :", type="password")
    if st.button("🔓 Se connecter", type="primary", use_container_width=True):
        if hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.session_state.auth_time = time.time()
            st.rerun()
        else:
            st.error("❌ Mot de passe incorrect")
    st.stop()

if not check_authentication():
    show_login_page()

# ================= FONCTION DE TRANSFORMATION AUTOMATIQUE =================

def parse_xml_dynamic(file_obj):
    """Transforme le XML en Excel en prenant TOUTES les colonnes automatiquement"""
    try:
        file_obj.seek(0)
        tree = ET.parse(file_obj) # Plus rapide et moins de mémoire que fromstring
        root = tree.getroot()
        
        dataframes = {}

        # On cherche les sections principales (Ventes, Tickets, Paiements)
        # On définit les balises qui contiennent des lignes de données
        sections_to_extract = {
            'SALE_LINES': ['.//LINE', './/ITEM', './/SALE_LINE'],
            'TICKETS': ['.//TICKET', './/VALID_TICKET'],
            'MEDIA_LINES': ['.//MEDIA', './/PAYMENT'],
            'TRANSACTIONS': ['.//TRANSACTION'],
            'STORE_INFO': ['.//STORE_INFO']
        }

        for sheet_name, xpaths in sections_to_extract.items():
            all_rows = []
            for xpath in xpaths:
                elements = root.findall(xpath)
                for elem in elements:
                    # EXTRACTION DYNAMIQUE : On prend tout ce qui existe dans la balise
                    row = {}
                    
                    # 1. On prend les attributs (ex: STOREID, TICKETNUMBER)
                    row.update(elem.attrib)
                    
                    # 2. On prend tous les enfants (ex: price, barcode, taxAmount, etc.)
                    for child in elem:
                        # Si l'enfant a lui-même des enfants, on peut concaténer (optionnel)
                        if len(child) == 0:
                            row[child.tag] = child.text
                        else:
                            # Pour les sous-balises (comme les taxes complexes)
                            for subchild in child:
                                row[f"{child.tag}_{subchild.tag}"] = subchild.text
                    
                    all_rows.append(row)
            
            if all_rows:
                # Création du DataFrame et conversion automatique des chiffres
                df = pd.DataFrame(all_rows)
                for col in df.columns:
                    df[col] = pd.to_numeric(df[col].str.replace(',', '.'), errors='ignore')
                dataframes[sheet_name] = df

        # Nettoyage mémoire
        del root
        del tree
        gc.collect()
        
        return dataframes
    except Exception as e:
        st.error(f"Erreur lors de la lecture du XML : {e}")
        return None

def create_excel(dataframes):
    """Génère le fichier Excel"""
    output = io.BytesIO()
    try:
        # On utilise xlsxwriter car il est plus léger pour les gros fichiers
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in dataframes.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        output.seek(0)
        return output
    except:
        return None

# ================= INTERFACE =================

st.set_page_config(page_title="XML/Excel Converter", layout="wide")
st.markdown('<h1 style="text-align: center; color: #1E3A8A;">🔄 XML vers Excel PRO</h1>', unsafe_allow_html=True)

uploaded_files = st.file_uploader("Sélectionnez vos fichiers XML", type=['xml'], accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Transformer en Excel", type="primary", use_container_width=True):
        for file in uploaded_files:
            with st.spinner(f"Traitement de {file.name}..."):
                dfs = parse_xml_dynamic(file)
                if dfs:
                    excel_file = create_excel(dfs)
                    if excel_file:
                        st.success(f"✅ {file.name} terminé !")
                        st.download_button(
                            label=f"📥 Télécharger {file.name}.xlsx",
                            data=excel_file,
                            file_name=f"{file.name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=file.name
                        )
                else:
                    st.error(f"Impossible de lire {file.name}")
