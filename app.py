# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import re
import io

# ---------------------------
# OCR for Scanned PDFs
# ---------------------------
def extract_text_from_scanned_pdf(pdf_file):
    """Extract text from scanned PDFs using OCR."""
    images = convert_from_path(pdf_file)
    extracted_text = []
    for img in images:
        text = pytesseract.image_to_string(img)
        extracted_text.extend(text.split("\n"))
    return extracted_text

# ---------------------------
# Extraction Functions for Each Bank
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

# 🏦 Wio Bank Extraction
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

                    transactions.append([date.strip(), ref_number.strip(), description.strip(), amount.replace(',', '').strip(), running_balance.replace(',', '').strip()])
    return transactions

# 🏦 ABC Bank Extraction
def extract_abc_bank_transactions(pdf_file):
    transactions = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    date = parts[0]
                    description = " ".join(parts[1:-2])
                    amount = parts[-2]
                    balance = parts[-1]
                    transactions.append([date, description, amount, balance])
    return transactions

# 🏦 FAB Bank Extraction (Newly Added)
def extract_fab_transactions(pdf_file):
    transactions = []
    date_pattern = r'(\d{2} [A-Z]{3} \d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'

    with pdfplumber.open(pdf_file) as pdf:
        lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split("\n"))

    current_transaction = []
    for line in lines:
        if re.match(date_pattern, line):
            if current_transaction:
                transactions.append(current_transaction)
            current_transaction = [line]
        elif current_transaction:
            current_transaction.append(line)

    if current_transaction:
        transactions.append(current_transaction)

    extracted_data = []
    for trans in transactions:
        full_text = " ".join(trans)
        date_match = re.search(date_pattern, full_text)
        date = date_match.group(1) if date_match else ""

        values = re.findall(amount_pattern, full_text)
        balance = values[-1] if values else ""
        credit = values[-2] if len(values) > 1 else "0.00"
        debit = values[-3] if len(values) > 2 else "0.00"

        description = full_text
        for item in [date, debit, credit, balance]:
            description = description.replace(str(item), "").strip()

        extracted_data.append([date, date, description, debit, credit, balance])

    return extracted_data

# ---------------------------
# Streamlit Interface
# ---------------------------
st.set_page_config(page_title="Multi-Bank PDF Extractor with OCR", layout="wide")

st.header("🏦 PDF to Excel Converter - Multi-Bank & OCR Support")

# 📌 Bank Selection Dropdown
bank_choice = st.selectbox("Select Your Bank:", ["FAB Bank", "Wio Bank", "ABC Bank", "Scanned PDF (OCR)"])

# 📤 PDF Upload
uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    all_transactions = []
    with st.spinner(f"Processing {bank_choice}..."):

        for file in uploaded_pdfs:
            if bank_choice == "FAB Bank":
                transactions = extract_fab_transactions(file)
            elif bank_choice == "Wio Bank":
                transactions = extract_wio_transactions(file)
            elif bank_choice == "ABC Bank":
                transactions = extract_abc_bank_transactions(file)
            elif bank_choice == "Scanned PDF (OCR)":
                extracted_text = extract_text_from_scanned_pdf(file)
                transactions = [[line] for line in extracted_text]  # OCR just extracts text

            for transaction in transactions:
                transaction.append(file.name)
            all_transactions.extend(transactions)

    if all_transactions:
        columns = ["Date", "Value Date", "Description", "Debit", "Credit", "Balance", "Source File"] if bank_choice != "Scanned PDF (OCR)" else ["Extracted Text", "Source File"]
        df = pd.DataFrame(all_transactions, columns=columns)

        st.success("Transactions extracted successfully!")
        st.dataframe(df, use_container_width=True)

        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)

        st.download_button(
            label="⬇️ Download Extracted Data",
            data=buffer,
            file_name="extracted_transactions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No transactions found.")
else:
    st.info("Upload PDF files to start the extraction process.")
