import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io

def safe_float(value):
    if value is None: return 0.0
    try:
        return float(str(value).replace(',', '.'))
    except:
        return 0.0

def analyze_xml_headers(file_obj):
    file_obj.seek(0)
    tree = ET.parse(file_obj)
    root = tree.getroot()
    
    ticket_data = []
    
    # On cherche les balises TICKET (En-tête)
    # C'est ici que l'ETL trouve généralement le vrai montant
    for ticket in root.iter():
        if ticket.tag in ['TICKET', 'VALID_TICKET', 'SALE']:
            
            # 1. On cherche les différentes valeurs de total stockées dans l'en-tête
            total_ttc = safe_float(ticket.findtext('totalSale') or ticket.findtext('TOTAL_AMOUNT') or ticket.findtext('totalAmount'))
            total_net = safe_float(ticket.findtext('totalNet') or ticket.findtext('TOTAL_NET'))
            total_tax = safe_float(ticket.findtext('taxAmount') or ticket.findtext('TAX_AMOUNT'))
            
            # Parfois la taxe est dans une sous-balise TAXES
            if total_tax == 0:
                tax_elem = ticket.find('.//TAX_AMOUNT') or ticket.find('.//taxValue')
                if tax_elem is not None:
                    total_tax = safe_float(tax_elem.text)

            # On n'ajoute que si le ticket a une valeur
            if total_ttc != 0 or total_net != 0:
                ticket_data.append({
                    'Ticket_ID': ticket.get('TICKETNUMBER') or ticket.get('TICKET_ID') or ticket.findtext('serial'),
                    'Total_TTC_Header': total_ttc,
                    'Total_Net_Header': total_net,
                    'Taxe_Header': total_tax,
                    'Calcul_Verif': total_net + total_tax
                })

    return pd.DataFrame(ticket_data)

st.set_page_config(layout="wide")
st.title("🔍 Recherche du Montant ETL Manquant")

file = st.file_uploader("Charger le XML", type=['xml'])

if file:
    df_headers = analyze_xml_headers(file)
    
    if not df_headers.empty:
        st.subheader("Analyse des En-têtes (Tickets)")
        
        sum_ttc = df_headers['Total_TTC_Header'].sum()
        sum_net = df_headers['Total_Net_Header'].sum()
        sum_tax = df_headers['Taxe_Header'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Somme TTC Header", f"{sum_ttc:,.2f}")
        c2.metric("Somme Net Header", f"{sum_net:,.2f}")
        c3.metric("Somme Taxes Header", f"{sum_tax:,.2f}")
        c4.metric("Cible ETL", "180,173.38")

        # Calcul de l'écart
        diff = 180173.38 - sum_ttc
        if abs(diff) < 1:
            st.success("🎯 MATCH ! Le montant TTC des en-têtes correspond à l'ETL.")
        else:
            st.error(f"❌ Écart de {diff:,.2f} par rapport à l'ETL")
            
        st.write("### Détail des 50 premiers tickets")
        st.dataframe(df_headers.head(50))
        
        # Option pour voir si la taxe est la clé
        if sum_tax > 0:
            st.info(f"Note : La taxe totale trouvée est de {sum_tax:,.2f}. Si on l'ajoute à votre ancien montant, est-on plus proche ?")
    else:
        st.error("Aucune balise de total (totalSale/TOTAL_AMOUNT) n'a été trouvée dans les en-têtes.")
