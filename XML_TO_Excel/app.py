import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import gc

def safe_float(value):
    if value is None: return 0.0
    try:
        return float(str(value).replace(',', '.'))
    except:
        return 0.0

def parse_xml_expert(file_obj):
    file_obj.seek(0)
    try:
        tree = ET.parse(file_obj)
        root = tree.getroot()
        
        all_lines = []

        # On parcourt TOUTES les balises qui ressemblent à une ligne de transaction
        # Inditex utilise souvent 'LINE' ou 'ITEM'
        for line in root.iter():
            if line.tag in ['LINE', 'ITEM', 'RETURN_LINE', 'SALE_LINE']:
                
                # On récupère TOUTES les variantes de prix possibles dans le XML
                qty = safe_float(line.findtext('quantity') or line.findtext('qty') or line.get('quantity'))
                unit_price = safe_float(line.findtext('price') or line.findtext('unitPrice'))
                gross_price = safe_float(line.findtext('orgPrice') or line.findtext('grossPrice'))
                net_amount = safe_float(line.findtext('netAmount') or line.findtext('totalNet'))
                tax_amount = safe_float(line.findtext('taxAmount') or line.findtext('tax'))
                discount = safe_float(line.findtext('discountAmount') or line.findtext('discount'))
                
                # Détection du type de ligne (Vente ou Retour)
                line_type = line.findtext('lineType') or line.tag
                # Si c'est un retour, la quantité doit souvent être négative
                if 'RETURN' in line_type.upper() and qty > 0:
                    qty = -qty

                data = {
                    'Ticket_ID': line.get('TICKETNUMBER') or line.get('TICKET_ID') or line.findtext('serial'),
                    'Type': line_type,
                    'Ref': line.findtext('barcode') or line.findtext('REFERENCE'),
                    'Quantite': qty,
                    'Prix_Unitaire_XML': unit_price,
                    'Prix_Brut_XML': gross_price,
                    'Remise_XML': discount,
                    'Taxe_XML': tax_amount,
                    # Calculs de vérification
                    'Total_Brut_Calcule': qty * unit_price,
                    'Total_Net_Calcule': (qty * unit_price) - discount + tax_amount,
                }
                all_lines.append(data)

        return pd.DataFrame(all_lines)
    except Exception as e:
        st.error(f"Erreur : {e}")
        return None

# --- Interface Streamlit ---
st.set_page_config(layout="wide")
st.title("🔍 Diagnostic de Différence ETL")

file = st.file_uploader("Charger le XML de 7.8 Mo", type=['xml'])

if file:
    df = parse_xml_expert(file)
    
    if df is not None:
        # Affichage des totaux pour diagnostic
        col1, col2, col3 = st.columns(3)
        
        total_brut = df['Total_Brut_Calcule'].sum()
        total_net = df['Total_Net_Calcule'].sum()
        
        col1.metric("Votre Total Actuel (Brut)", f"{total_brut:,.2f}")
        col2.metric("Total Net (Avec Taxe/Remise)", f"{total_net:,.2f}")
        col3.metric("Cible ETL", "180,173.38")

        st.write("### Analyse des écarts")
        diff_brut = 180173.38 - total_brut
        diff_net = 180173.38 - total_net
        
        st.warning(f"Écart restant si on utilise le Net + Taxes : **{diff_net:,.2f}**")

        # Export Excel complet pour audit
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Details')
        
        st.download_button("📥 Télécharger l'Audit complet pour comparer avec l'ETL", 
                           output.getvalue(), 
                           file_name="audit_indigo.xlsx")
        
        st.write("#### Aperçu des données extraites :")
        st.dataframe(df.head(100))
