# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile

# ✅ Streamlit Page Configuration
st.set_page_config(page_title="PDF to Excel Categorization Tool", layout="wide")

# ---------------------------
# Helper Functions
# ---------------------------

def extract_wio_transactions(pdf_file):
    """Extract transactions from Wio Bank statements using IBAN-based currency mapping from the first page."""
    transactions = []
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'
    iban_pattern = r'(AE\d{22})'  # Matches IBAN (23 characters starting with AE)
    currency_pattern = r'CURRENCY[:\s-]*([A-Z]{3})'  # Improved regex for currency extraction
    balance_pattern = r'(AE\d{22})\s+([\d,]+\.\d{2})\s*([A-Z]{3})'  # Extracts IBAN, Balance, Currency

    account_currency_map = {}  # Stores { IBAN: Currency }
    default_iban, default_currency = None, None  # Default IBAN & Currency

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # **Step 1: Extract IBAN & Currency from the First Page (Summary Table)**
            if page_num == 0:
                matches = re.findall(balance_pattern, text)
                for match in matches:
                    account_currency_map[match[0]] = match[2]  # Store { IBAN: Currency }

                print("DEBUG: Extracted IBAN & Currency Mapping:", account_currency_map)

            # **Step 2: Extract Default IBAN & Currency from the Transaction Header**
            if "ACCOUNT NUMBER" in text and "IBAN" in text:
                iban_match = re.search(iban_pattern, text)
                currency_match = re.search(currency_pattern, text)

                if iban_match:
                    default_iban = iban_match.group(1)
                if currency_match:
                    extracted_currency = currency_match.group(1)
                    print("DEBUG: Extracted Currency from Header ->", extracted_currency)  
                    default_currency = extracted_currency

                print("DEBUG: Default IBAN:", default_iban, "Default Currency:", default_currency)

            # **Step 3: Extract Transactions**
            for line in text.strip().split("\n"):
                iban_match = re.search(iban_pattern, line)  # Check if IBAN exists
                if iban_match:
                    current_iban = iban_match.group(1)
                else:
                    current_iban = default_iban  # Use default IBAN if not found

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

                    # **Assign Correct Currency Based on IBAN**
                    currency = account_currency_map.get(current_iban, default_currency)

                    if currency is None:
                        currency = "Unknown"  # Safety fallback in case currency is still missing
                        print(f"WARNING: Currency missing for IBAN {current_iban}, assigning 'Unknown'.")

                    transactions.append([
                        date.strip(),
                        ref_number.strip(),
                        description.strip(),
                        amount.replace(",", "").strip(),
                        running_balance.replace(",", "").strip(),
                        currency,
                        current_iban  # Store IBAN for tracking
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
