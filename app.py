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
    
    # Convert BytesIO to a temporary file for PyMuPDF
    temp_pdf_path = "temp_fab_statement.pdf"
    with open(temp_pdf_path, "wb") as temp_pdf:
        temp_pdf.write(pdf_file.read())
    
    # Extract text using PyMuPDF (fitz)
    doc = fitz.open(temp_pdf_path)
    combined_text += "\n".join([page.get_text("text") for page in doc])
    doc.close()
    
    # Extract text using pdfplumber
    pdf_file.seek(0)
    with pdfplumber.open(pdf_file) as pdf:
        combined_text += "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    # Extract full descriptions using regex with multi-line support
    full_desc_pattern = re.compile(
        r"(\d{2} \w{3} \d{4})\s+(\d{2} \w{3} \d{4})\s+(.+?)\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})",
        re.MULTILINE,
    )

    matches = list(full_desc_pattern.finditer(combined_text))

    for match in matches:
        date, value_date, description, debit, credit, balance = match.groups()
        transactions.append([
            date.strip() if date else "",  # Date
            value_date.strip() if value_date else "",  # Value Date
            description.strip() if description else "",  # Full Description
            float(debit.replace(',', '')) if debit else 0.00,  # Debit
            float(credit.replace(',', '')) if credit else 0.00,  # Credit
            float(balance.replace(',', '')) if balance else 0.00,  # Balance
            "",  # Placeholder for Source File
            float(balance.replace(',', '')) if balance else 0.00,  # Extracted Balance
            0.00,  # Placeholder for Amount Column
            0.00  # Placeholder for FAB Running Balance
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

with tabs[0]:
    st.header("PDF to Excel Converter")
    
    bank_selection = st.selectbox("Select Bank:", ["FAB (First Abu Dhabi Bank)", "Wio Bank"])
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_pdfs:
        opening_balance = st.number_input("Enter Opening Balance:", value=0.0, step=0.01)
        all_transactions = []
        
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                if bank_selection == "FAB (First Abu Dhabi Bank)":
                    transactions = extract_fab_transactions(file)
                elif bank_selection == "Wio Bank":
                    transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)  # Append file name as source
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Value Date", "Full Description", "Debit (AED)", "Credit (AED)", "Balance (AED)", "Source File", "Extracted Balance", "Amount", "FAB Running Balance"] if bank_selection == "FAB (First Abu Dhabi Bank)" else ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)
            
            # Save consolidated data to Excel
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            
            st.success("Transactions extracted successfully!")
            st.dataframe(df, use_container_width=True)
            st.download_button(
                label="⬇️ Download Consolidated Excel",
                data=output,
                file_name="consolidated_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No transactions found.")
