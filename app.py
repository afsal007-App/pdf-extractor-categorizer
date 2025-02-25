# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile
from streamlit.components.v1 import html

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

def extract_wio_transactions(pdf_file):
    """Extract transactions from Wio Bank PDF statements."""
    transactions = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.strip().split('\n'):
                date_match = re.match(r'(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()
                    ref_number_match = re.search(r'(P\d{9})', remainder)
                    ref_number = ref_number_match.group(1) if ref_number_match else ""
                    remainder_clean = remainder.replace(ref_number, "").strip() if ref_number else remainder
                    numbers = re.findall(r'-?\d{1,3}(?:,\\d{3})*(?:\\.\\d{1,2})?', remainder_clean)

                    if len(numbers) >= 2:
                        amount, running_balance = numbers[-2], numbers[-1]
                        description = re.sub(rf'\s*{re.escape(amount)}\s*{re.escape(running_balance)}$', '', remainder_clean).strip()
                    elif len(numbers) == 1:
                        amount = numbers[0]
                        running_balance = ""
                        description = re.sub(rf'\s*{re.escape(amount)}$', '', remainder_clean).strip()
                    else:
                        continue

                    transactions.append([date, ref_number, description, amount, running_balance])
    return transactions

# ---------------------------
# Streamlit Interface
# ---------------------------

st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide")
tabs = st.tabs(["PDF to Excel Converter", "Categorization"])

if 'converted_file' not in st.session_state:
    st.session_state['converted_file'] = None

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
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount", "Running Balance"]
            df = pd.DataFrame(all_transactions, columns=columns)
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')

            st.success("Transactions extracted successfully.")
            st.dataframe(df, use_container_width=True)

            # Swipe button for categorization
            swipe_button = """
            <style>
                .swipe-btn {
                    width: 250px; height: 50px;
                    border-radius: 25px;
                    background: linear-gradient(135deg, #2ecc71, #27ae60);
                    color: white; font-size: 16px; font-weight: bold;
                    text-align: center; line-height: 50px; cursor: pointer;
                    animation: heartbeat 1.5s infinite ease-in-out;
                }
                @keyframes heartbeat {
                    0% { transform: scale(1); }
                    25% { transform: scale(1.1); }
                    50% { transform: scale(1); }
                    75% { transform: scale(1.1); }
                    100% { transform: scale(1); }
                }
            </style>
            <div class="swipe-btn" onclick="streamlitSend({type: 'SWIPE'})">Swipe to Categorize</div>
            <script>
                function streamlitSend(message) {
                    const streamlit = window.parent;
                    streamlit.postMessage(message, "*");
                }
            </script>
            """

            html(swipe_button)

            # Transfer data upon swipe
            if st.experimental_get_query_params().get("action") == ["categorize"]:
                st.session_state['converted_file'] = df
                st.success("File transferred to categorization section.")
        else:
            st.error("No transactions available.")
    else:
        st.info("Please upload PDF files to begin conversion.")

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.header("Categorization")

    if st.session_state['converted_file'] is not None:
        st.success("Converted file ready for categorization.")
        st.dataframe(st.session_state['converted_file'].head(), use_container_width=True)
    else:
        st.info("Upload and convert a PDF to categorize transactions.")
