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
    
    # Extract full descriptions using regex with multi-line support
    full_desc_pattern = re.compile(
        r"(\d{2} \w{3} \d{4})\s+(\d{2} \w{3} \d{4})\s+(.+?)\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})",
        re.MULTILINE,
    )

    matches = list(full_desc_pattern.finditer(combined_text))

    # Extract transactions with extended descriptions
    for match in matches:
        date, value_date, description, debit, credit, balance = match.groups()
        
        # Find where the match occurs in the text
        start_idx = match.start()
        end_idx = match.end()
        
        # Extend the description to capture additional lines of text following the transaction line
        extended_desc = combined_text[start_idx:end_idx+500].split("\n")
        
        # Filter out unnecessary lines and concatenate meaningful ones
        final_desc = " ".join([line.strip() for line in extended_desc if line.strip()])
        
        transactions.append([
            date.strip() if date else "",  # Date
            value_date.strip() if value_date else "",  # Value Date
            final_desc.strip() if final_desc else "",  # Full Description
            float(debit.replace(',', '')) if debit else 0.00,  # Debit
            float(credit.replace(',', '')) if credit else 0.00,  # Credit
            float(balance.replace(',', '')) if balance else 0.00,  # Balance
            float(balance.replace(',', '')) if balance else 0.00,  # Extracted Balance Column
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
    
    # Add bank selection dropdown
    bank_selection = st.selectbox("Select Bank:", ["FAB (First Abu Dhabi Bank)"])
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_pdfs:
        opening_balance = st.number_input("Enter Opening Balance:", value=0.0, step=0.01)
        all_transactions = []
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                transactions = extract_fab_transactions(file)
                for transaction in transactions:
                    transaction[-1] = file.name  # Update source file
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Value Date", "Full Description", "Debit (AED)", "Credit (AED)", "Balance (AED)", "Extracted Balance (AED)", "Amount", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)
            
            # Ensure 'Extracted Balance (AED)' is numeric before calculation
            df["Extracted Balance (AED)"] = pd.to_numeric(df["Extracted Balance (AED)"], errors='coerce').fillna(0.00)
            
            # Compute Amount column correctly
            df["Amount"] = df["Extracted Balance (AED)"].diff()
            df.loc[0, "Amount"] = df.loc[0, "Extracted Balance (AED)"] - opening_balance  # First row adjustment
            df["Amount"] = df["Amount"].fillna(0.00)  # Ensure no NaN values
            
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
