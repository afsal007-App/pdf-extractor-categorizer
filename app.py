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

def extract_wio_transactions(pdf_file):
    """Extract transactions from Wio Bank statements using IBAN-based currency mapping."""
    transactions = []
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'
    iban_pattern = r'(AE\d{22})'  # Matches IBAN (23 characters starting with AE)
    currency_pattern = r'CURRENCY[:\s-]*([A-Z]{3})'  # Improved regex for currency extraction
    balance_pattern = r'(AE\d{22})\s+[\d,]+\.\d{2}\s*([A-Z]{3})'  # Extracts IBAN, Balance, Currency

    account_currency_map = {}  # Stores { IBAN: Currency }
    current_iban, current_currency = None, None  # Default IBAN & Currency

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # **Step 1: Extract IBAN & Currency from the First Page (Summary Table)**
            if page_num == 0:
                matches = re.findall(balance_pattern, text)
                for match in matches:
                    account_currency_map[match[0]] = match[1]  # Store { IBAN: Currency }
                print("DEBUG: Extracted IBAN & Currency Mapping:", account_currency_map)

            # **Step 2: Detect Transaction Headers & Update IBAN and Currency**
            if "ACCOUNT NUMBER" in text and "IBAN" in text:
                header_iban_match = re.search(iban_pattern, text)
                header_currency_match = re.search(currency_pattern, text)

                if header_iban_match:
                    detected_iban = header_iban_match.group(1)
                    if detected_iban in account_currency_map:
                        current_iban = detected_iban
                        print(f"DEBUG: Matched IBAN in Summary: {current_iban}")

                if header_currency_match:
                    extracted_currency = header_currency_match.group(1)
                    if current_iban and extracted_currency == account_currency_map.get(current_iban, None):
                        current_currency = extracted_currency
                        print(f"DEBUG: Matched Currency for IBAN {current_iban}: {current_currency}")

            # **Step 3: Extract Transactions**
            for line in text.strip().split("\n"):
                date_match = re.match(date_pattern, line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()

                    # Remove reference number if present at the beginning
                    ref_number_match = re.match(r'(P\d{9})\s+', remainder)
                    ref_number = ref_number_match.group(1) if ref_number_match else ""
                    if ref_number:
                        remainder = remainder[len(ref_number):].strip()

                    # Extract Amount & Running Balance
                    numbers = re.findall(amount_pattern, remainder)
                    if not numbers:
                        continue

                    amount = numbers[-2] if len(numbers) >= 2 else ""
                    running_balance = numbers[-1] if len(numbers) >= 1 else ""
                    description = remainder.replace(amount, "").replace(running_balance, "").strip()

                    # **Assign Correct IBAN & Currency**
                    assigned_iban = current_iban
                    assigned_currency = account_currency_map.get(assigned_iban, current_currency)

                    if assigned_currency is None:
                        assigned_currency = "Unknown"  # Safety fallback

                    transactions.append([
                        date.strip(),
                        ref_number.strip(),
                        description.strip(),
                        amount.replace(",", "").strip(),
                        running_balance.replace(",", "").strip(),
                        assigned_currency,
                        assigned_iban  # Store IBAN for tracking
                    ])

    return transactions

def save_to_excel(df, filename="output.xlsx"):
    """Save DataFrame to Excel and return as BytesIO."""
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

# ---------------------------
# Streamlit Interface
# ---------------------------

# Initialize session state
if 'converted_file' not in st.session_state:
    st.session_state['converted_file'] = None

# Tabs for navigation
tabs = st.tabs(["PDF to Excel Converter"])

# ---------------------------
# PDF to Excel Converter Tab
# ---------------------------
with tabs[0]:
    st.header("PDF to Excel Converter")
    st.write("Upload your PDF statements to convert them into Excel format with IBAN-based currency tracking.")

    uploaded_pdfs = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_pdfs:
        all_transactions = []
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Currency", "IBAN", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)

            # Data cleaning
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df['Amount (Incl. VAT)'] = pd.to_numeric(df['Amount (Incl. VAT)'], errors='coerce')
            df['Running Balance (Extracted)'] = pd.to_numeric(df['Running Balance (Extracted)'], errors='coerce')
            df = df.dropna(subset=["Date", "Amount (Incl. VAT)"]).reset_index(drop=True)

            st.success("Transactions extracted successfully with IBAN-based Currency Mapping!")
            st.dataframe(df, use_container_width=True)

            # ✅ Download with the new currency column
            output = save_to_excel(df, filename="converted_transactions_with_currency.xlsx")
            st.download_button(
                label="Download Converted Excel",
                data=output,
                file_name="converted_transactions_with_currency.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("Upload PDF files to begin conversion.")
