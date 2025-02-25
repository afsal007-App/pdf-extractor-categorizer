# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile

# ---------------------------
# Page Config and Styling
# ---------------------------
st.set_page_config(page_title="📄 PDF & Excel Categorization Tool", layout="wide", page_icon="📊")

st.markdown("""
<style>
    body {
        background-color: #f7f9fc;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        padding: 10px 20px;
        border-radius: 8px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stFileUploader > div {
        border: 2px dashed #aaa;
        border-radius: 10px;
        padding: 15px;
        background-color: #fff;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 16px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text for matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

def extract_wio_transactions(pdf_file):
    """Extract transactions from Wio Bank statements."""
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
                        amount.replace(',', '').strip(),
                        running_balance.replace(',', '').strip()
                    ])
    return transactions

def find_description_column(columns):
    """Identify the description column."""
    possible = ['description', 'details', 'narration', 'particulars', 'transaction details', 'remarks']
    return next((col for col in columns if any(name in col.lower() for name in possible)), None)

def load_master_file():
    """Load the master categorization file."""
    try:
        url = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"
        df = pd.read_excel(url)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f"🚨 Error loading master file: {e}")
        return pd.DataFrame()

def save_to_excel(df):
    """Convert DataFrame to BytesIO Excel file."""
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

def categorize_description(description, master_df):
    """Categorize description based on master keywords."""
    cleaned = clean_text(description)
    for _, row in master_df.iterrows():
        if row['Key Word'] and row['Key Word'] in cleaned:
            return row['Category']
    return 'Uncategorized'

def categorize_statement(statement_df, master_df, desc_col):
    """Categorize the statement DataFrame."""
    statement_df['Categorization'] = statement_df[desc_col].apply(lambda x: categorize_description(x, master_df))
    return statement_df

# ---------------------------
# Initialize Session State
# ---------------------------
if 'converted_file_json' not in st.session_state:
    st.session_state['converted_file_json'] = None

# ---------------------------
# UI Layout
# ---------------------------
st.title("📑 PDF & Excel Categorization Tool")
st.caption("🚀 Effortlessly convert PDF bank statements into categorized Excel sheets.")

tabs = st.tabs(["🔄 PDF to Excel Converter", "🏷️ Categorization"])

# ---------------------------
# PDF to Excel Converter Tab
# ---------------------------
with tabs[0]:
    st.header("🔄 PDF to Excel Converter")
    uploaded_pdfs = st.file_uploader("📤 Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_pdfs:
        all_transactions = []
        with st.spinner("🔍 Extracting transactions..."):
            for file in uploaded_pdfs:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)

            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df['Amount (Incl. VAT)'] = pd.to_numeric(df['Amount (Incl. VAT)'], errors='coerce')
            df['Running Balance (Extracted)'] = pd.to_numeric(df['Running Balance (Extracted)'], errors='coerce')

            df = df.dropna(subset=["Date", "Amount (Incl. VAT)"]).reset_index(drop=True)

            opening_balance = st.number_input("💰 Enter Opening Balance:", value=0.0, step=0.01)
            df['Calculated Balance'] = opening_balance + df['Amount (Incl. VAT)'].cumsum()

            st.success("✅ Transactions extracted successfully!")
            st.dataframe(df, use_container_width=True)

            if st.button("➡️ Prepare for Categorization"):
                st.session_state['converted_file_json'] = df.to_json()
                st.success("📂 Converted file saved for categorization!")

            output = save_to_excel(df)
            st.download_button(
                label="⬇️ Download Excel",
                data=output,
                file_name="converted_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ No transactions found.")
    else:
        st.info("ℹ️ Upload PDF files to start the conversion process.")

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.header("🏷️ Categorization")
    master_df = load_master_file()

    if master_df.empty:
        st.error("❌ Master categorization file could not be loaded.")
    else:
        uploaded_excels = st.file_uploader("📥 Upload Excel/CSV files", type=["xlsx", "csv"], accept_multiple_files=True)
        files_to_categorize = list(uploaded_excels) if uploaded_excels else []

        if st.session_state['converted_file_json'] and st.checkbox("Include Converted File for Categorization"):
            converted_df = pd.read_json(st.session_state['converted_file_json'])
            files_to_categorize.append(converted_df)

        if files_to_categorize:
            categorized_files = []
            for file in files_to_categorize:
                filename = "Converted_File.xlsx" if isinstance(file, pd.DataFrame) else file.name
                df = file if isinstance(file, pd.DataFrame) else pd.read_excel(file)
                desc_col = find_description_column(df.columns)

                if desc_col:
                    categorized_df = categorize_statement(df, master_df, desc_col)
                    st.subheader(f"📊 Preview: {filename}")
                    st.dataframe(categorized_df.head(10), use_container_width=True)

                    buffer = save_to_excel(categorized_df)
                    categorized_files.append((filename, buffer))

                    st.download_button(
                        label=f"⬇️ Download {filename}",
                        data=buffer,
                        file_name=f"Categorized_{filename}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning(f"⚠️ No description column found in {filename}.")

            if len(categorized_files) > 1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zipf:
                    for fname, data in categorized_files:
                        zipf.writestr(f"Categorized_{fname}", data.getvalue())
                zip_buffer.seek(0)

                st.download_button(
                    label="⬇️ Download All as ZIP",
                    data=zip_buffer,
                    file_name="Categorized_Files.zip",
                    mime="application/zip"
                )
        else:
            st.info("ℹ️ Upload files or use the converted file to categorize.")

