import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os
import io
import zipfile

st.set_page_config(
    page_title="Extracteur XML ItxCloseExport",
    page_icon="📊",
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
    .success-box {
        background-color: #D1FAE5;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #10B981;
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
</style>
""", unsafe_allow_html=True)


def parse_xml_to_dataframes(xml_content, is_file_path=True):
    """Parse le contenu XML et retourne des DataFrames"""
    try:
        if is_file_path:
            tree = ET.parse(xml_content)
        else:
            tree = ET.ElementTree(ET.fromstring(xml_content))

        root = tree.getroot()
        dataframes = {}

        # Fonction helper pour extraire les données d'une section
        def extract_section(xpath, element_name, attributes=None, fields=None):
            data = []
            elements = root.findall(xpath)

            for elem in elements:
                row = {}

                # Ajouter les attributs
                if attributes:
                    for attr in attributes:
                        row[attr] = elem.get(attr)

                # Ajouter les champs
                if fields:
                    for field in fields:
                        field_elem = elem.find(field)
                        row[field] = field_elem.text if field_elem is not None else None

                data.append(row)

            if data:
                return pd.DataFrame(data)
            return pd.DataFrame()

        # 1. SALE_LINES
        sale_lines_attrs = ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER']
        sale_lines_fields = [
            'barcode', 'description', 'quantity', 'price', 'orgPrice',
            'date', 'time', 'familyCode', 'subFamilyCode', 'isVoidLine',
            'lineNumber', 'campaign', 'lineType', 'employeeId', 'campaignYear',
            'period', 'departmentId', 'operationTypeGroup', 'controlCode'
        ]
        df_sale = extract_section('.//SALE_LINES/LINE', 'LINE', sale_lines_attrs, sale_lines_fields)
        if not df_sale.empty:
            dataframes['SALE_LINES'] = df_sale

        # 2. VALID_TICKETS
        ticket_attrs = ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER', 'DOCUMENTUUID']
        ticket_fields = [
            'serial', 'date', 'time', 'operatorId', 'totalSale', 'totalNet',
            'isVoidTicket', 'employeeId', 'fiscalprinterId', 'operationTypeGroup', 'roundingError'
        ]
        df_tickets = extract_section('.//VALID_TICKETS/TICKET', 'TICKET', ticket_attrs, ticket_fields)
        if not df_tickets.empty:
            dataframes['VALID_TICKETS'] = df_tickets

        # 3. MEDIA_LINES
        media_attrs = ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER']
        media_fields = ['serial', 'date', 'time', 'paid', 'returned', 'paymentMethod']
        df_media = extract_section('.//MEDIA_LINES/MEDIA', 'MEDIA', media_attrs, media_fields)
        if not df_media.empty:
            dataframes['MEDIA_LINES'] = df_media

        # 4. VOIDED_TICKETS
        voided_attrs = ['STOREID', 'POSNUMBER', 'OPERATIONNUMBER', 'OPERATIONTYPE', 'TICKETNUMBER', 'DOCUMENTUUID']
        voided_fields = [
            'time', 'operatorId', 'voidedserial', 'voidedoperationNumber',
            'voidedPosNumber', 'voidedstoreId', 'originalUID'
        ]
        df_voided = extract_section('.//VOIDED_TICKETS/TICKET_VOID', 'TICKET_VOID', voided_attrs, voided_fields)
        if not df_voided.empty:
            dataframes['VOIDED_TICKETS'] = df_voided

        # 5. TRANSACTIONS
        trans_fields = [
            'code', 'description', 'debit', 'credit', 'auxValue', 'auxValue2',
            'taxPercent', 'employeeId', 'universalId', 'txType'
        ]
        df_trans = extract_section('.//TRANSACTIONS/TRANSACTION', 'TRANSACTION', None, trans_fields)
        if not df_trans.empty:
            dataframes['TRANSACTIONS'] = df_trans

        # 6. WARNINGS
        warn_fields = ['warningType', 'warningMessage', 'posNumber', 'refoperationNumber']
        df_warn = extract_section('.//WARNINGS/WARNING', 'WARNING', None, warn_fields)
        if not df_warn.empty:
            dataframes['WARNINGS'] = df_warn

        # 7. STORE_INFO
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
        st.error(f"Erreur lors du parsing XML: {str(e)}")
        return {}


def create_excel_file(dataframes):
    """Crée un fichier Excel en mémoire avec plusieurs onglets"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dataframes.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    output.seek(0)
    return output


def main():
    # En-tête de l'application
    st.markdown('<h1 class="main-header">📊 Extracteur XML ItxCloseExport</h1>', unsafe_allow_html=True)

    # Sidebar pour la configuration
    with st.sidebar:
        st.markdown("**INDIGO COMPANY / INDITEX**")
        st.markdown("### ⚙️ Configuration")
        st.markdown("**INTTT**")
        
        st.markdown("---")
        st.info("""
        **Fonctionnalités:**
        - Upload manuel des fichiers XML
        - Extraction de toutes les sections
        - Export Excel multi-onglets
        - Prévisualisation des données
        """)

    # Contenu principal
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📁 Upload de fichiers")

        # Upload manuel seulement
        uploaded_files = st.file_uploader(
            "Téléchargez vos fichiers XML ItxCloseExport",
            type=['xml'],
            accept_multiple_files=True,
            help="Sélectionnez un ou plusieurs fichiers XML à traiter"
        )

        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} fichier(s) téléchargé(s)")
            
            # Afficher la liste des fichiers
            st.markdown("#### 📋 Fichiers uploadés:")
            for i, file in enumerate(uploaded_files, 1):
                file_size = len(file.getvalue()) / 1024  # Taille en KB
                with st.expander(f"{i}. {file.name} ({file_size:.1f} KB)"):
                    st.code(f"Taille: {file_size:.1f} KB")
                    st.caption(f"Type: {file.type}")

    with col2:
        st.markdown("### 📈 Statistiques")
        if uploaded_files:
            st.metric("Fichiers XML", len(uploaded_files))

            # Aperçu des sections disponibles
            if st.button("📊 Analyser la structure", key="analyze_structure"):
                if uploaded_files:
                    sample_file = uploaded_files[0]
                    content = sample_file.getvalue().decode('utf-8')
                    dataframes = parse_xml_to_dataframes(content, is_file_path=False)
                    
                    if dataframes:
                        st.markdown("#### Sections détectées:")
                        for sheet_name, df in dataframes.items():
                            st.markdown(f"- **{sheet_name}**: {len(df)} lignes")
                    else:
                        st.warning("Aucune section détectée dans le fichier")

    # Traitement des fichiers
    if uploaded_files:
        st.markdown("---")
        st.markdown("### ⚡ Traitement")

        if st.button("🚀 Traiter tous les fichiers", type="primary", key="process_files"):
            all_results = {}

            with st.spinner("Traitement en cours..."):
                progress_bar = st.progress(0)

                for idx, file_obj in enumerate(uploaded_files):
                    try:
                        # Mettre à jour la barre de progression
                        progress = (idx + 1) / len(uploaded_files)
                        progress_bar.progress(progress)

                        # Traiter le fichier
                        content = file_obj.getvalue().decode('utf-8')
                        dataframes = parse_xml_to_dataframes(content, is_file_path=False)
                        file_name = file_obj.name

                        if dataframes:
                            all_results[file_name] = dataframes

                            # Afficher un aperçu
                            with st.expander(f"📄 {file_name}", expanded=False):
                                selected_sheet = st.selectbox(
                                    "Choisir une section à prévisualiser:",
                                    list(dataframes.keys()),
                                    key=f"preview_{idx}"
                                )

                                if selected_sheet in dataframes:
                                    df_preview = dataframes[selected_sheet]
                                    st.dataframe(df_preview.head(10))
                                    st.caption(f"Aperçu de {selected_sheet} ({len(df_preview)} lignes au total)")

                    except Exception as e:
                        st.error(f"Erreur avec {file_obj.name}: {str(e)}")

                progress_bar.empty()

                # Exporter les résultats
                if all_results:
                    st.markdown("---")
                    st.markdown("### 💾 Exporter les résultats")

                    # Options d'export - SEULEMENT EXCEL
                    for file_name, dataframes in all_results.items():
                        base_name = os.path.splitext(file_name)[0]

                        st.markdown(f"#### 📦 {file_name}")

                        # Bouton Excel uniquement
                        excel_file = create_excel_file(dataframes)
                        st.download_button(
                            label="📥 Télécharger Excel (.xlsx)",
                            data=excel_file,
                            file_name=f"{base_name}_export.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"excel_{file_name}"
                        )

                    # Résumé global
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.markdown("### ✅ Traitement terminé avec succès!")
                    st.markdown(f"**Fichiers traités:** {len(all_results)}")
                    total_rows = sum(
                        len(df)
                        for file_data in all_results.values()
                        for df in file_data.values()
                    )
                    st.markdown(f"**Lignes extraites au total:** {total_rows:,}")
                    st.markdown("</div>", unsafe_allow_html=True)

                else:
                    st.warning("Aucune donnée n'a pu être extraite des fichiers.")


if __name__ == "__main__":
    main()
