import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import hashlib
import time
import gc

# ================= CONFIGURATION =================
APP_PASSWORD = "Indigo2025**"
PASSWORD_HASH = hashlib.sha256(APP_PASSWORD.encode()).hexdigest()

def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

def show_login_page():
    st.title("🔒 Connexion")
    password = st.text_input("Mot de passe :", type="password")
    if st.button("Se connecter"):
        if hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect")
    st.stop()

# ================= MOTEUR D'EXTRACTION DE PRÉCISION =================

def safe_float(value):
    """Convertit proprement les textes en nombres pour Excel"""
    if value is None: return 0.0
    try:
        return float(str(value).replace(',', '.'))
    except:
        return 0.0

def parse_xml_deep(file_obj):
    """Analyse récursive pour ne rater aucune ligne de vente"""
    file_obj.seek(0)
    try:
        tree = ET.parse(file_obj)
        root = tree.getroot()
        
        results = {
            'VENTES_DETAILS': [],
            'TICKETS_RECAP': [],
            'PAIEMENTS': [],
            'ANNULATIONS': []
        }

        # 1. EXTRACTION DES LIGNES DE VENTE (SALE_LINES / ITEM)
        # On cherche partout dans le document pour ne rien rater
        for line in root.iter():
            # Format Standard (LINE) ou Format COM (ITEM)
            if line.tag in ['LINE', 'ITEM']:
                parent_ticket = None
                # Tentative de récupération des infos du ticket parent (remonte l'arbre)
                # Note: Cette partie dépend de la structure, on prend les attributs si dispo
                data = {
                    'Ticket_ID': line.get('TICKETNUMBER') or line.get('TICKET_ID'),
                    'Barcode': (line.findtext('barcode') or line.findtext('BARCODE') or line.findtext('REFERENCE')),
                    'Description': (line.findtext('description') or line.findtext('DESCRIPTION')),
                    'Quantite': safe_float(line.findtext('quantity') or line.findtext('QUANTITY') or line.get('quantity')),
                    'Prix_Unitaire': safe_float(line.findtext('price') or line.findtext('PRICE') or line.get('price')),
                    'Total_Ligne': safe_float(line.findtext('total') or 0.0),
                    'Date': line.findtext('date') or line.findtext('DATE'),
                    'Est_Annule': line.findtext('isVoidLine') or 'false'
                }
                # Calcul de vérification automatique
                data['Verif_Calcul_Total'] = data['Quantite'] * data['Prix_Unitaire']
                results['VENTES_DETAILS'].append(data)

            # 2. EXTRACTION DES RÉCAPITULATIFS TICKETS (VALID_TICKETS)
            elif line.tag in ['TICKET', 'VALID_TICKET']:
                if line.findtext('totalSale') or line.findtext('TOTAL_AMOUNT'):
                    t_data = {
                        'Ticket_ID': line.get('TICKETNUMBER') or line.get('TICKET_ID') or line.findtext('serial'),
                        'Date': line.findtext('date'),
                        'Heure': line.findtext('time'),
                        'Total_TTC': safe_float(line.findtext('totalSale') or line.findtext('TOTAL_AMOUNT')),
                        'Total_Net': safe_float(line.findtext('totalNet')),
                        'Vendeur': line.findtext('operatorId') or line.findtext('EMPLOYEE_ID'),
                        'Statut_Annule': line.findtext('isVoidTicket') or 'false'
                    }
                    results['TICKETS_RECAP'].append(t_data)

            # 3. PAIEMENTS (MEDIA_LINES)
            elif line.tag in ['MEDIA', 'PAYMENT']:
                p_data = {
                    'Ticket_ID': line.get('TICKETNUMBER'),
                    'Mode_Paiement': line.findtext('paymentMethod') or line.findtext('MEDIA_ID'),
                    'Montant': safe_float(line.findtext('paid') or line.findtext('AMOUNT'))
                }
                results['PAIEMENTS'].append(p_data)

        # Conversion en DataFrames
        output_dfs = {}
        for key, rows in results.items():
            if rows:
                output_dfs[key] = pd.DataFrame(rows)
        
        return output_dfs

    except Exception as e:
        st.error(f"Erreur technique : {e}")
        return None

# ================= INTERFACE =================

if not check_authentication():
    show_login_page()

st.set_page_config(page_title="Indigo Precision Tool", layout="wide")
st.title("📊 Extracteur XML Haute Précision")
st.markdown("Ce mode analyse chaque balise du fichier pour garantir qu'aucun ticket n'est oublié.")

uploaded_files = st.file_uploader("Charger fichiers XML", type=['xml'], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        with st.expander(f"📁 Analyse de {file.name}", expanded=True):
            dfs = parse_xml_deep(file)
            
            if dfs and 'VENTES_DETAILS' in dfs:
                df_ventes = dfs['VENTES_DETAILS']
                
                # Statistiques de contrôle
                col1, col2, col3 = st.columns(3)
                col1.metric("Lignes trouvées", len(df_ventes))
                col2.metric("Total Quantités", f"{df_ventes['Quantite'].sum():.0f}")
                col3.metric("Valeur Totale", f"{df_ventes['Verif_Calcul_Total'].sum():.2f} €")

                # Bouton de téléchargement
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    for sheet_name, df in dfs.items():
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                st.download_button(
                    label="📥 Télécharger l'Excel complet",
                    data=output.getvalue(),
                    file_name=f"PRECISION_{file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.success(f"Analyse terminée. Vérifiez la colonne 'Verif_Calcul_Total' dans l'Excel.")
            else:
                st.error("Aucune donnée de vente trouvée dans ce format XML.")
