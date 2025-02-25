# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile

# ---------------------------
# Page Configuration & Styles
# ---------------------------
st.set_page_config(page_title="🎨 PDF & Excel Categorization Tool", layout="wide", page_icon="📊")

st.markdown("""
<style>
/* Global Settings */
html, body {
    background-color: #1a1c1e;
    font-family: 'Segoe UI', sans-serif;
    color: #e0e0e0;
}

h1, h2, h3 {
    font-weight: 700;
    background: -webkit-linear-gradient(45deg, #ff6ec4, #7873f5);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 2px 2px 8px rgba(0,0,0,0.3);
}

.stButton>button {
    background: linear-gradient(135deg, #42a5f5, #7e57c2);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 25px;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.stButton>button:hover {
    transform: scale(1.08);
    background: linear-gradient(135deg, #7e57c2, #42a5f5);
    box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.4);
}

.stFileUploader > div {
    border: 2px dashed #42a5f5;
    border-radius: 15px;
    background-color: rgba(255, 255, 255, 0.05);
    padding: 20px;
    transition: background-color 0.3s ease;
}

.stFileUploader > div:hover {
    background-color: rgba(66, 165, 245, 0.1);
}

.stTabs [data-baseweb="tab"] {
    font-size: 17px;
    font-weight: bold;
    color: #ffffff;
    background-color: #282a36;
    padding: 10px 20px;
    border-radius: 10px 10px 0 0;
    transition: all 0.3s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    background-color: #44475a;
}

.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
}

.css-1q8dd3e {
    background-color: #21222c;
    padding: 15px;
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------
# Helper Functions
# ---------------------------

def clean_text(text):
    """Clean and standardize text."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

def extract_wio_transactions(pdf_file):
    """Extract transactions from PDF."""
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
                        description = description.replace(item, '').strip()
                    transactions.append([date.strip(), ref_number.strip(), description.strip(), amount.replace(',', '').strip(), running_balance.replace(',', '').strip()])
    return transactions

def load_master_file():
    """Load master categorization file."""
    try:
        url = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"
        df = pd.read_excel(url)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f"🚨 Error loading master file: {e}")
        return pd.DataFrame()

def save_to_excel(df):
    """Save DataFrame to Excel."""
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

def categorize_description(description, master_df):
    """Categorize transaction based on description."""
    cleaned = clean_text(description)
    for _, row in master_df.iterrows():
        if row['Key Word'] and row['Key Word'] in cleaned:
            return row['Category']
    return 'Uncategorized'

def categorize_statement(df, master_df, desc_col):
    """Apply categorization."""
    df['Categorization'] = df[desc_col].apply(lambda x: categorize_description(x, master_df))
    return df

# ---------------------------
# Session State Initialization
# ---------------------------
if 'converted_file_json' not in st.session_state:
    st.session_state['converted_file_json'] = None

# ---------------------------
# User Interface Layout
# ---------------------------
st.title("🎨 PDF & Excel Categorization Tool")
st.caption("✨ Convert PDF bank statements into beautifully categorized Excel sheets with ease!")

tabs = st.tabs(["🔄 PDF to Excel", "🏷️ Categorization"])

# ---------------------------
# PDF to Excel Tab
# ---------------------------
with tabs[0]:
    st.header("🔄 Upload PDF and Convert to Excel")
    uploaded_pdfs = st.file_uploader("📤 Drag & drop your PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_pdfs:
        with st.spinner("🔍 Extracting data..."):
            transactions = []
            for pdf in uploaded_pdfs:
                extracted = extract_wio_transactions(pdf)
                for tran in extracted:
                    tran.append(pdf.name)
                transactions.extend(extracted)

        if transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance", "Source File"]
            df = pd.DataFrame(transactions, columns=columns)
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df['Amount (Incl. VAT)'] = pd.to_numeric(df['Amount (Incl. VAT)'], errors='coerce')

            opening_balance = st.number_input("💵 Enter Opening Balance:", value=0.0, step=0.01)
            df['Calculated Balance'] = opening_balance + df['Amount (Incl. VAT)'].cumsum()

            st.success("✅ Data extracted successfully!")
            st.dataframe(df, use_container_width=True)

            if st.button("➡️ Save for Categorization"):
                st.session_state['converted_file_json'] = df.to_json()
                st.success("📂 Saved for next step!")

            st.download_button("⬇️ Download Excel", data=save_to_excel(df), file_name="transactions.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.header("🏷️ Categorize Your Transactions")
    master_df = load_master_file()

    if master_df.empty:
        st.error("❌ Failed to load master file.")
    else:
        uploaded_excels = st.file_uploader("📥 Upload Excel/CSV files for categorization", type=["xlsx", "csv"], accept_multiple_files=True)
        files = list(uploaded_excels)

        if st.session_state['converted_file_json'] and st.checkbox("Include Converted File"):
            files.append(pd.read_json(st.session_state['converted_file_json']))

        if files:
            for file in files:
                df = file if isinstance(file, pd.DataFrame) else pd.read_excel(file)
                desc_col = next((col for col in df.columns if 'description' in col.lower()), None)

                if desc_col:
                    categorized_df = categorize_statement(df, master_df, desc_col)
                    st.subheader(f"📊 Preview:")
                    st.dataframe(categorized_df.head(10), use_container_width=True)

                    buffer = save_to_excel(categorized_df)
                    st.download_button("⬇️ Download Categorized File", data=buffer, file_name="categorized_transactions.xlsx")
                else:
                    st.warning("⚠️ Description column not found.")
        else:
            st.info("ℹ️ Upload a file or select the converted file.")
