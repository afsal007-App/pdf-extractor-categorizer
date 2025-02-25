# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import pdfplumber
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
                # Match date at the beginning of the line
                date_match = re.match(date_pattern, line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()

                    # Extract reference number
                    ref_number_match = re.search(r'(P\d{9})', remainder)
                    ref_number = ref_number_match.group(1) if ref_number_match else ""

                    # Extract amounts from the end of the line
                    numbers = re.findall(amount_pattern, remainder)
                    amount = numbers[-2] if len(numbers) >= 2 else ""
                    running_balance = numbers[-1] if len(numbers) >= 1 else ""

                    # Extract description (by removing known patterns)
                    description = remainder
                    if ref_number:
                        description = description.replace(ref_number, "").strip()
                    if amount:
                        description = description.replace(amount, "").strip()
                    if running_balance:
                        description = description.replace(running_balance, "").strip()

                    transactions.append([
                        date,
                        ref_number,
                        description,
                        amount.replace(',', ''),
                        running_balance.replace(',', '')
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
    """Load the master categorization file from a remote source."""
    try:
        url = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"
        df = pd.read_excel(url)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f"Error loading master file: {e}")
        return pd.DataFrame()

# ---------------------------
# Streamlit Interface
# ---------------------------

st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide")
tabs = st.tabs(["PDF to Excel Converter", "Categorization"])

# Session State Initialization
if 'converted_file' not in st.session_state:
    st.session_state['converted_file'] = None

# ---------------------------
# PDF to Excel Converter Tab
# ---------------------------
with tabs[0]:
    st.header("PDF to Excel Converter")
    bank_options = ["Wio Bank"]
    selected_bank = st.selectbox("Select Bank:", bank_options)
    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_pdfs:
        all_transactions = []
        with st.spinner("Extracting transactions..."):
            for file in uploaded_pdfs:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df['Amount (Incl. VAT)'] = df['Amount (Incl. VAT)'].replace({',': ''}, regex=True).astype(float)
            df['Running Balance (Extracted)'] = pd.to_numeric(df['Running Balance (Extracted)'].replace({',': ''}, regex=True), errors='coerce')
            df = df.dropna(subset=["Date"]).sort_values(by="Date").reset_index(drop=True)

            opening_balance = st.number_input("Enter Opening Balance:", value=0.0, step=0.01)
            df['Calculated Balance'] = opening_balance + df['Amount (Incl. VAT)'].cumsum()

            st.success("Transactions extracted successfully!")
            st.dataframe(df, use_container_width=True)

            # Store converted file in session state for categorization
            if st.button("Prepare for Categorization"):
                st.session_state['converted_file'] = df
                st.success("File ready for categorization!")

            # Download button for the converted Excel file
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            st.download_button("Download Converted Excel", data=output, file_name="converted_transactions.xlsx")
        else:
            st.warning("No transactions found.")
    else:
        st.info("Upload PDF files to start the conversion process.")

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.header("Categorization")
    master_df = load_master_file()

    if master_df.empty:
        st.error("Master categorization file could not be loaded.")
    else:
        uploaded_excels = st.file_uploader("Upload Excel/CSV files for categorization", type=["xlsx", "csv"], accept_multiple_files=True)
        files_to_categorize = uploaded_excels or []

        # Include converted file from the previous tab if available
        if st.session_state['converted_file'] is not None:
            if st.button("Add Converted File to Categorization"):
                files_to_categorize = [st.session_state['converted_file']]

        if files_to_categorize:
            categorized_files = []
            for file in files_to_categorize:
                if isinstance(file, pd.DataFrame):
                    df = file
                else:
                    df = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)

                desc_col = find_description_column(df.columns)
                if desc_col:
                    categorized_df = categorize_statement(df, master_df, desc_col)
                    buffer = io.BytesIO()
                    categorized_df.to_excel(buffer, index=False)
                    buffer.seek(0)
                    categorized_files.append((file if isinstance(file, pd.DataFrame) else file.name, buffer))

                    st.success(f"{file if isinstance(file, pd.DataFrame) else file.name} categorized successfully.")
                    st.dataframe(categorized_df.head(), use_container_width=True)

                    st.download_button(
                        label=f"Download Categorized {file if isinstance(file, pd.DataFrame) else file.name}",
                        data=buffer,
                        file_name=f"Categorized_{file if isinstance(file, pd.DataFrame) else file.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error(f"No description column found in {file if isinstance(file, pd.DataFrame) else file.name}.")

            # ZIP download option if multiple files are categorized
            if len(categorized_files) > 1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zipf:
                    for fname, data in categorized_files:
                        zipf.writestr(f"Categorized_{fname}", data.getvalue())
                zip_buffer.seek(0)

                st.download_button(
                    label="Download All Categorized Files as ZIP",
                    data=zip_buffer,
                    file_name="Categorized_Files.zip",
                    mime="application/zip"
                )
        else:
            st.info("Upload files or use the converted file to begin categorization.")
