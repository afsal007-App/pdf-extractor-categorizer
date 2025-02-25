# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

# Function to trigger tab switch
switch_script = """
<script>
    function switchToCategorization() {
        var streamlit = window.parent;
        streamlit.postMessage({ type: "switch-tab", value: "Categorization" }, "*");
    }
</script>
"""

heartbeat_button = """
<style>
    .heartbeat {
        display: inline-block;
        font-size: 16px;
        font-weight: bold;
        color: white;
        background: linear-gradient(135deg, #2ecc71, #27ae60);
        padding: 12px 24px;
        border-radius: 10px;
        border: none;
        cursor: pointer;
        animation: heartbeat 1.5s infinite;
        transition: transform 0.2s;
    }
    @keyframes heartbeat {
        0% { transform: scale(1); }
        25% { transform: scale(1.1); }
        50% { transform: scale(1); }
        75% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
</style>
"""

def extract_wio_transactions(pdf_file):
    """Improved extraction for Wio Bank statements with validation."""
    transactions = []
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.strip().split('\n')
            for line in lines:
                date_match = re.match(date_pattern, line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()
                    ref_number_match = re.search(r'(P\d{9})', remainder)
                    ref_number = ref_number_match.group(1) if ref_number_match else ""
                    numbers = re.findall(amount_pattern, remainder)

                    if len(numbers) < 1:
                        continue

                    amount = numbers[-2] if len(numbers) >= 2 else ""
                    running_balance = numbers[-1] if len(numbers) >= 1 else ""

                    description = remainder
                    for item in [ref_number, amount, running_balance]:
                        if item:
                            description = description.replace(item, '').strip()

                    transactions.append([
                        date.strip(),
                        ref_number.strip(),
                        description.strip(),
                        amount.replace(',', '').strip(),
                        running_balance.replace(',', '').strip()
                    ])
    return transactions

# ---------------------------
# Streamlit Interface
# ---------------------------

st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide")

# Store the selected tab in session state
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = "PDF to Excel Converter"

tabs = st.tabs(["PDF to Excel Converter", "Categorization"])

# Switch tabs when button is clicked
if st.session_state.selected_tab == "Categorization":
    st.session_state.selected_tab = "Categorization"

# ---------------------------
# PDF to Excel Converter Tab
# ---------------------------
with tabs[0]:
    st.header("PDF to Excel Converter")
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_pdfs:
        all_transactions = []
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)

            # Clean and convert columns
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df['Amount (Incl. VAT)'] = pd.to_numeric(df['Amount (Incl. VAT)'], errors='coerce')
            df['Running Balance (Extracted)'] = pd.to_numeric(df['Running Balance (Extracted)'], errors='coerce')

            df = df.dropna(subset=["Date", "Amount (Incl. VAT)"]).reset_index(drop=True)

            st.success("Transactions extracted successfully!")
            st.dataframe(df, use_container_width=True)

            st.markdown(heartbeat_button, unsafe_allow_html=True)

            if st.button("Prepare for Categorization", key="categorization_button"):
                st.session_state['converted_file'] = df
                st.session_state.selected_tab = "Categorization"
                st.success("File added to Categorization!")
                st.markdown(switch_script, unsafe_allow_html=True)
                st.markdown("<script>switchToCategorization();</script>", unsafe_allow_html=True)

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.header("Categorization")
    if "converted_file" in st.session_state and st.session_state["converted_file"] is not None:
        st.success("File successfully transferred from the converter.")
        st.dataframe(st.session_state["converted_file"], use_container_width=True)
    else:
        st.info("No converted file available. Please go to the PDF Converter tab.")

