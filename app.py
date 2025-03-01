# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile

# ✅ Streamlit Page Configuration
st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide")

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

@st.cache_data
def extract_wio_transactions(pdf_file):
    """Extract transactions from Wio Bank statements using IBAN-based currency mapping."""
    transactions = []
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'
    account_pattern = r'(AE\d{22})'
    balance_pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})\s?([A-Z]{3})'

    account_currency_map = {}  # Mapping IBAN to currency
    current_account = None

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # Extract account number and currency from the first page summary
            if page_num == 0:
                account_matches = re.findall(account_pattern, text)
                balance_matches = re.findall(balance_pattern, text)

                # Create a dictionary mapping account IBAN to currency
                for acc, bal in zip(account_matches, balance_matches):
                    account_currency_map[acc] = bal[1]

            for line in text.strip().split('\n'):
                # Detect account number in transaction details
                account_match = re.search(account_pattern, line)
                if account_match:
                    current_account = account_match.group(1)

                # Extract transaction details
                date_match = re.match(date_pattern, line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()
                    ref_number_match = re.search(r'(P\d{9})', remainder)
                    ref_number = ref_number_match.group(1) if ref_number_match else ""
                    numbers = re.findall(amount_pattern, remainder)
                    if not numbers:
                        continue

                    amount = numbers[-2] if len(numbers) >= 2 else ""
                    running_balance = numbers[-1] if len(numbers) >= 1 else ""

                    description = remainder
                    for item in [ref_number, amount, running_balance]:
                        description = description.replace(item, '').strip()

                    # Assign currency based on the detected account number
                    currency = account_currency_map.get(current_account, "Unknown")

                    transactions.append([
                        date.strip(),
                        ref_number.strip(),
                        description.strip(),
                        amount.replace(',', '').strip(),
                        running_balance.replace(',', '').strip(),
                        currency  # Assigned based on IBAN mapping
                    ])

    return transactions

# ---------------------------
# Streamlit Interface
# ---------------------------

# Store extracted data persistently
if "transactions" not in st.session_state:
    st.session_state["transactions"] = None

st.header("PDF to Excel Converter")
st.write("Upload your PDF statements to extract transactions with currency tracking.")

uploaded_pdfs = st.file_uploader(
    "Upload PDF files", type=["pdf"], accept_multiple_files=True
)

if uploaded_pdfs and st.button("Process PDF Transactions"):
    all_transactions = []
    with st.spinner("Extracting transactions..."):
        for file in uploaded_pdfs:
            transactions = extract_wio_transactions(file)
            for transaction in transactions:
                transaction.append(file.name)
            all_transactions.extend(transactions)

    if all_transactions:
        columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Currency", "Source File"]
        df = pd.DataFrame(all_transactions, columns=columns)

        # Data cleaning
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
        df['Amount (Incl. VAT)'] = pd.to_numeric(df['Amount (Incl. VAT)'], errors='coerce')
        df['Running Balance (Extracted)'] = pd.to_numeric(df['Running Balance (Extracted)'], errors='coerce')
        df = df.dropna(subset=["Date", "Amount (Incl. VAT)"]).reset_index(drop=True)

        # Store data in session state to prevent loss
        st.session_state["transactions"] = df

        st.success("Transactions extracted successfully with Currency Mapping!")
        st.dataframe(df, use_container_width=True)

if st.session_state["transactions"] is not None:
    st.download_button(
        label="Download Converted Excel",
        data=save_to_excel(st.session_state["transactions"], filename="converted_transactions_with_currency.xlsx"),
        file_name="converted_transactions_with_currency.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
