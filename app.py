import streamlit as st
import pandas as pd
import pdfplumber
import PyPDF2
import fitz  # PyMuPDF
import re
import io

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

# Extract transactions from Emirates NBD statements
def extract_emirates_nbd_transactions(pdf_file):
    transactions = []
    combined_text = ""
    
    # Extract text using multiple PDF parsing libraries
    pdf_file.seek(0)
    reader = PyPDF2.PdfReader(pdf_file)
    for page in reader.pages:
        combined_text += page.extract_text() + "\n"
    
    pdf_file.seek(0)
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                combined_text += extracted_text + "\n"
    
    # Regular expression for transactions (Date, Value Date, Description, Debit, Credit, Balance)
    transaction_pattern = re.compile(
        r"(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})",
        re.MULTILINE,
    )
    
    for match in transaction_pattern.finditer(combined_text):
        date, value_date, description, debit, credit, balance = match.groups()
        transactions.append([
            date.strip(),
            value_date.strip(),
            description.strip(),
            float(debit.replace(',', '')) if debit else 0.00,
            float(credit.replace(',', '')) if credit else 0.00,
            float(balance.replace(',', '')) if balance else 0.00,
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
    
    bank_selection = st.selectbox("Select Bank:", ["FAB (First Abu Dhabi Bank)", "Wio Bank", "Emirates NBD"])
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_pdfs:
        opening_balance = st.number_input("Enter Opening Balance:", value=0.0, step=0.01)
        all_transactions = []
        
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                if bank_selection == "FAB (First Abu Dhabi Bank)":
                    transactions = extract_fab_transactions(file)
                    df_fab = pd.DataFrame(transactions, columns=["Date", "Value Date", "Full Description", "Debit (AED)", "Credit (AED)", "Balance (AED)", "Source File", "Extracted Balance", "Amount", "FAB Running Balance"])
                elif bank_selection == "Wio Bank":
                    transactions = extract_wio_transactions(file)
                    df_wio = pd.DataFrame(transactions, columns=["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"])
                elif bank_selection == "Emirates NBD":
                    transactions = extract_emirates_nbd_transactions(file)
                    df_enbd = pd.DataFrame(transactions, columns=["Date", "Value Date", "Description", "Debit (AED)", "Credit (AED)", "Balance (AED)", "Source File"])
                all_transactions.extend(transactions)

        if all_transactions:
            st.success("Transactions extracted successfully!")
            if bank_selection == "FAB (First Abu Dhabi Bank)":
                st.dataframe(df_fab, use_container_width=True)
            elif bank_selection == "Wio Bank":
                st.dataframe(df_wio, use_container_width=True)
            elif bank_selection == "Emirates NBD":
                st.dataframe(df_enbd, use_container_width=True)
            
            output = io.BytesIO()
            if bank_selection == "FAB (First Abu Dhabi Bank)":
                df_fab.to_excel(output, index=False)
            elif bank_selection == "Wio Bank":
                df_wio.to_excel(output, index=False)
            elif bank_selection == "Emirates NBD":
                df_enbd.to_excel(output, index=False)
            output.seek(0)
            
            st.download_button(
                label="⬇️ Download Converted Excel",
                data=output,
                file_name=f"converted_transactions_{bank_selection.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No transactions found.")
