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

# ---------------------------
# WIO BANK Extraction Code
# ---------------------------

def extract_wio_transactions(pdf_file):
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
                        ""  
                    ])
    return transactions

# ---------------------------
# FAB Extraction Code
# ---------------------------

def extract_fab_transactions(pdf_file):
    transactions = []
    combined_text = ""
    
    temp_pdf_path = "temp_fab_statement.pdf"
    with open(temp_pdf_path, "wb") as temp_pdf:
        temp_pdf.write(pdf_file.read())
    
    doc = fitz.open(temp_pdf_path)
    combined_text += "\n".join([page.get_text("text") for page in doc])
    doc.close()
    
    pdf_file.seek(0)
    with pdfplumber.open(pdf_file) as pdf:
        combined_text += "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    full_desc_pattern = re.compile(
        r"(\d{2} \w{3} \d{4})\s+(\d{2} \w{3} \d{4})\s+(.+?)\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})?\s+([\d,]*\.\d{2})",
        re.MULTILINE,
    )

    matches = list(full_desc_pattern.finditer(combined_text))

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

# ---------------------------
# Emirates NBD Extraction Code
# ---------------------------

def extract_emirates_nbd_transactions(pdf_file):
    transactions = []
    combined_text = ""
    
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
            ""  
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
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                if bank_selection == "FAB (First Abu Dhabi Bank)":
                    transactions = extract_fab_transactions(file)
                elif bank_selection == "Wio Bank":
                    transactions = extract_wio_transactions(file)
                elif bank_selection == "Emirates NBD":
                    transactions = extract_emirates_nbd_transactions(file)
                
                df = pd.DataFrame(transactions)
                st.dataframe(df, use_container_width=True)
                
                output = io.BytesIO()
                df.to_excel(output, index=False)
                output.seek(0)
                
                st.download_button(
                    label="⬇️ Download Converted Excel",
                    data=output,
                    file_name=f"converted_transactions_{bank_selection.lower().replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
