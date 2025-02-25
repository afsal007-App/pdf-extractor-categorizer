
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# ---------------------------
# Helper Functions
# ---------------------------

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

def save_to_excel(df):
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

# ---------------------------
# Streamlit Interface
# ---------------------------

st.set_page_config(page_title="PDF & Excel Categorization Tool", layout="wide", page_icon="📊")

st.markdown(
    '''
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
    </style>
    ''', unsafe_allow_html=True
)

st.title("📥 PDF to Excel Converter")
st.subheader("Convert Wio Bank PDF statements into structured Excel files.")

uploaded_pdfs = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("🔍 Extracting transactions..."):
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
