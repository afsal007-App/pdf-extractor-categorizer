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

def extract_wio_transactions(pdf_file):
    """Extract transactions from Wio Bank statements using account number for currency mapping."""
    transactions = []
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'
    account_pattern = r'(AE\d{22})'
    balance_pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})\s([A-Z]{3})'

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

def find_description_column(columns):
    """Identify the description column in the DataFrame."""
    possible = ['description', 'details', 'narration', 'particulars', 'transaction details', 'remarks']
    return next((col for col in columns if any(name in col.lower() for name in possible)), None)

def categorize_description(description, master_df):
    """Assign category based on keywords from the master DataFrame."""
    cleaned = clean_text(description)
    for _, row in master_df.iterrows():
        if row['Key Word'] and row['Key Word'] in cleaned:
            return row['Category']
    return 'Uncategorized'

def categorize_statement(statement_df, master_df, desc_col):
    """Categorize transactions in the provided DataFrame."""
    statement_df['Categorization'] = statement_df[desc_col].apply(lambda x: categorize_description(x, master_df))
    return statement_df

def load_master_file():
    """Load the master categorization file."""
    try:
        url = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"
        df = pd.read_excel(url)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f"Error loading master file: {e}")
        return pd.DataFrame()

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
tabs = st.tabs(["PDF to Excel Converter", "Categorization"])

# ---------------------------
# PDF to Excel Converter Tab
# ---------------------------
with tabs[0]:
    st.header("PDF to Excel Converter")
    st.write("Upload your PDF statements to convert them into Excel format with currency tracking.")

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
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Currency", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)

            # Data cleaning
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df['Amount (Incl. VAT)'] = pd.to_numeric(df['Amount (Incl. VAT)'], errors='coerce')
            df['Running Balance (Extracted)'] = pd.to_numeric(df['Running Balance (Extracted)'], errors='coerce')
            df = df.dropna(subset=["Date", "Amount (Incl. VAT)"]).reset_index(drop=True)

            st.success("Transactions extracted successfully with Currency Mapping!")
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

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.header("Categorization")
    st.write("Categorize your transactions based on predefined keywords.")

    master_df = load_master_file()

    if master_df.empty:
        st.error("Master categorization file could not be loaded.")
    else:
        uploaded_excels = st.file_uploader(
            "Upload Excel/CSV files",
            type=["xlsx", "csv"],
            accept_multiple_files=True
        )

        if uploaded_excels:
            for file in uploaded_excels:
                df = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)

                desc_col = find_description_column(df.columns)
                if desc_col:
                    categorized_df = categorize_statement(df, master_df, desc_col)
                    st.subheader(f"Categorized Transactions - {file.name}")
                    st.dataframe(categorized_df, use_container_width=True)

                    buffer = save_to_excel(categorized_df, filename=f"Categorized_{file.name}")
                    st.download_button(
                        label=f"Download {file.name}",
                        data=buffer,
                        file_name=f"Categorized_{file.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
