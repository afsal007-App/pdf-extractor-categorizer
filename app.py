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

                    # Skip if no amounts found
                    if len(numbers) < 1:
                        continue

                    amount = numbers[-2] if len(numbers) >= 2 else ""
                    running_balance = numbers[-1] if len(numbers) >= 1 else ""

                    # Extract and clean description
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
                        ""
                    ])
    return transactions

def extract_fab_transactions(pdf_file):
    """Extraction function for FAB (First Abu Dhabi Bank) statements using PyMuPDF, PyPDF2, and pdfplumber."""
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
    
    # Extract text using PyPDF2
    pdf_file.seek(0)
    reader = PyPDF2.PdfReader(pdf_file)
    for page in reader.pages:
        combined_text += page.extract_text() if page.extract_text() else ""
    
    # Extract text using pdfplumber
    pdf_file.seek(0)
    with pdfplumber.open(pdf_file) as pdf:
        combined_text += "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    # Extract full descriptions using regex
    full_desc_pattern = re.compile(
        r"(\d{2} \w{3} \d{4})\s+(\d{2} \w{3} \d{4})\s+(.+?)\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})",
        re.MULTILINE,
    )

    matches = list(full_desc_pattern.finditer(combined_text))

    # Extract transactions with extended descriptions
    for match in matches:
        date, value_date, description, debit, credit, balance = match.groups()
        transactions.append([
            date.strip(),
            value_date.strip(),
            description.strip(),
            float(debit.replace(',', '')) if debit else 0.00,
            float(credit.replace(',', '')) if credit else 0.00,
            float(balance.replace(',', '')) if balance else 0.00,
            float(balance.replace(',', '')) if balance else 0.00  # Extracted Balance Column
        ])
    return transactions

# ---------------------------
# Streamlit Interface
# ---------------------------

st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide")
tabs = st.tabs(["PDF to Excel Converter", "Categorization"])

with tabs[0]:
    st.header("PDF to Excel Converter")
    
    # Add bank selection dropdown
    bank_selection = st.selectbox("Select Bank:", ["Wio Bank", "FAB (First Abu Dhabi Bank)"])
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_pdfs:
        opening_balance = st.number_input("Enter Opening Balance:", value=0.0, step=0.01)
        all_transactions = []
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                if bank_selection == "Wio Bank":
                    transactions = extract_wio_transactions(file)
                elif bank_selection == "FAB (First Abu Dhabi Bank)":
                    transactions = extract_fab_transactions(file)
                
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Value Date", "Description", "Debit (AED)", "Credit (AED)", "Balance (AED)", "Extracted Balance (AED)", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)

            # Calculate balance using opening balance
            df["Balance (AED)"] = opening_balance + df["Credit (AED)"].astype(float) - df["Debit (AED)"].astype(float)
            
            st.success("Transactions extracted successfully!")
            st.dataframe(df, use_container_width=True)
            
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            
            st.download_button(
                label="⬇️ Download Converted Excel",
                data=output,
                file_name="converted_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No transactions found.")
