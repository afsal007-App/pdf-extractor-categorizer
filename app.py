# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import zipfile
from streamlit_lottie import st_lottie
import requests

# ---------------------------
# Helper Functions
# ---------------------------

def load_lottieurl(url: str):
    """Load Lottie animations from URL."""
    response = requests.get(url)
    if response.status_code != 200:
        return None
    return response.json()

def clean_text(text):
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

def extract_wio_transactions(pdf_file):
    transactions = []
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    amount_pattern = r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)'

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.strip().split('\n'):
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
                        date.strip(), ref_number.strip(), description.strip(),
                        amount.replace(',', '').strip(),
                        running_balance.replace(',', '').strip()
                    ])
    return transactions

def find_description_column(columns):
    possible = ['description', 'details', 'narration', 'particulars', 'transaction details', 'remarks']
    return next((col for col in columns if any(name in col.lower() for name in possible)), None)

def categorize_description(description, master_df):
    cleaned = clean_text(description)
    for _, row in master_df.iterrows():
        if row['Key Word'] and row['Key Word'] in cleaned:
            return row['Category']
    return 'Uncategorized'

def categorize_statement(statement_df, master_df, desc_col):
    statement_df['Categorization'] = statement_df[desc_col].apply(lambda x: categorize_description(x, master_df))
    return statement_df

def load_master_file():
    try:
        url = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"
        df = pd.read_excel(url)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f"Error loading master file: {e}")
        return pd.DataFrame()

def save_to_excel(df):
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

# ---------------------------
# UI/UX Setup
# ---------------------------

st.set_page_config(page_title="🌟 PDF & Excel Categorization Tool", layout="wide", page_icon="📊")

st.markdown(
    """
    <style>
        .stButton>button {
            border-radius: 10px;
            padding: 10px 20px;
            font-size: 16px;
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }
        .stButton>button:hover {
            background-color: #45a049;
        }
        .css-1aumxhk {
            font-family: 'Arial', sans-serif;
        }
        .main .block-container {
            padding-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True
)

# Lottie animations
lottie_loading = load_lottieurl("https://assets9.lottiefiles.com/private_files/lf30_t7z7oa.json")
lottie_success = load_lottieurl("https://assets9.lottiefiles.com/private_files/lf30_editor_mxyqnz5k.json")

# ---------------------------
# Streamlit Interface
# ---------------------------

tabs = st.tabs(["📥 PDF to Excel Converter", "📂 Categorization"])

if 'converted_file' not in st.session_state:
    st.session_state['converted_file'] = None

# ---------------------------
# PDF to Excel Converter Tab
# ---------------------------
with tabs[0]:
    st.title("📥 PDF to Excel Converter")
    st.subheader("Effortlessly convert your Wio Bank PDF statements into structured Excel files.")

    uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_pdfs:
        with st.spinner("🔍 Extracting transactions..."):
            st_lottie(lottie_loading, height=200)
            all_transactions = []
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

            if st.button("✨ Prepare for Categorization"):
                st.session_state['converted_file'] = df
                st_lottie(lottie_success, height=150)
                st.success("Converted file added to categorization!")

            output = save_to_excel(df)
            st.download_button(
                label="⬇️ Download Converted Excel",
                data=output,
                file_name="converted_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ No transactions found.")
    else:
        st.info("📄 Upload PDF files to start the conversion process.")

# ---------------------------
# Categorization Tab
# ---------------------------
with tabs[1]:
    st.title("📂 Transaction Categorization")
    st.subheader("Categorize transactions using a predefined master file.")

    master_df = load_master_file()
    if master_df.empty:
        st.error("⚠️ Master categorization file could not be loaded.")
    else:
        uploaded_excels = st.file_uploader("📁 Upload Excel/CSV files", type=["xlsx", "csv"], accept_multiple_files=True)
        files_to_categorize = list(uploaded_excels) if uploaded_excels else []

        if st.session_state['converted_file'] is not None and st.checkbox("✅ Include Converted File"):
            files_to_categorize.append(st.session_state['converted_file'])

        if files_to_categorize:
            categorized_files = []
            with st.spinner("🚀 Categorizing transactions..."):
                st_lottie(lottie_loading, height=150)
                for file in files_to_categorize:
                    filename = "Converted_File.xlsx" if isinstance(file, pd.DataFrame) else file.name
                    df = file if isinstance(file, pd.DataFrame) else pd.read_excel(file)

                    desc_col = find_description_column(df.columns)
                    if desc_col:
                        categorized_df = categorize_statement(df, master_df, desc_col)
                        buffer = save_to_excel(categorized_df)
                        categorized_files.append((filename, buffer))

                        st.subheader(f"🔎 Preview: {filename}")
                        st.dataframe(categorized_df.head(), use_container_width=True)

                        st.download_button(
                            label=f"⬇️ Download Categorized {filename}",
                            data=buffer,
                            file_name=f"Categorized_{filename}",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.error(f"⚠️ No description column found in {filename}.")

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
            st.info("📂 Upload files or select the converted file to start categorization.")
