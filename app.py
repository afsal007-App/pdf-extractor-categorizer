# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import pdfplumber
import PyPDF2
import fitz  # PyMuPDF
import re
import io
import zipfile

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

def extract_fab_transactions(pdf_file):
    """Extraction function for FAB (First Abu Dhabi Bank) statements."""
    transactions = []
    combined_text = ""
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                combined_text += text + "\n"
    
    st.write("📄 Extracted Text from FAB PDF:")
    st.code(combined_text[:500])  # Show first 500 characters for debugging

    full_desc_pattern = re.compile(
        r"(\d{2} \w{3} \d{4})\s+(\d{2} \w{3} \d{4})\s+(.+?)\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})",
        re.MULTILINE,
    )

    matches = list(full_desc_pattern.finditer(combined_text))
    st.write(f"🔍 Found {len(matches)} matching transactions in FAB PDF.")

    for match in matches:
        date, value_date, description, debit, credit, balance = match.groups()
        transactions.append([
            date.strip() if date else "",
            value_date.strip() if value_date else "",
            description.strip() if description else "",
            float(debit.replace(',', '')) if debit else 0.00,
            float(credit.replace(',', '')) if credit else 0.00,
            float(balance.replace(',', '')) if balance else 0.00,
            "",
            float(balance.replace(',', '')) if balance else 0.00,
            0.00,
            0.00
        ])
    return transactions

def extract_wio_transactions(pdf_file):
    """Improved extraction for Wio Bank statements."""
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
                        float(amount.replace(',', '')) if amount else 0.00,
                        float(running_balance.replace(',', '')) if running_balance else 0.00,
                        ""  # Placeholder for Source File
                    ])
    return transactions

# ---------------------------
# Streamlit Interface
# ---------------------------

st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide")
tabs = st.tabs(["PDF to Excel Converter", "Categorization"])

# Dictionary to store transactions for different banks
bank_dfs = {
    "FAB": pd.DataFrame(),
    "Wio Bank": pd.DataFrame(),
}

with tabs[0]:
    st.header("PDF to Excel Converter")
    
    bank_selection = st.selectbox("Select Bank:", ["FAB (First Abu Dhabi Bank)", "Wio Bank"])
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_pdfs:
        opening_balance = st.number_input("Enter Opening Balance:", value=0.0, step=0.01)
        
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                if bank_selection == "FAB (First Abu Dhabi Bank)":
                    transactions = extract_fab_transactions(file)
                    df_fab = pd.DataFrame(transactions, columns=["Date", "Value Date", "Full Description", "Debit (AED)", "Credit (AED)", "Balance (AED)", "Source File", "Extracted Balance", "Amount", "FAB Running Balance"])
                    if not df_fab.empty:
                        df_fab["Amount"] = df_fab["Extracted Balance"].diff().fillna(df_fab["Extracted Balance"].iloc[0] - opening_balance)
                        df_fab["FAB Running Balance"] = opening_balance + df_fab["Amount"].cumsum()
                    bank_dfs["FAB"] = pd.concat([bank_dfs["FAB"], df_fab], ignore_index=True)
                elif bank_selection == "Wio Bank":
                    transactions = extract_wio_transactions(file)
                    df_wio = pd.DataFrame(transactions, columns=["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"])
                    bank_dfs["Wio Bank"] = pd.concat([bank_dfs["Wio Bank"], df_wio], ignore_index=True)
        
        # Display extracted transactions preview
        st.subheader("Extracted Transactions Preview")
        if bank_selection in bank_dfs and not bank_dfs[bank_selection].empty:
            st.write(f"✅ Previewing {len(bank_dfs[bank_selection])} transactions for {bank_selection}.")
            st.dataframe(bank_dfs[bank_selection].head(50), use_container_width=True)
        else:
            st.warning(f"No transactions available for preview under {bank_selection}. Upload a PDF and try again.")
