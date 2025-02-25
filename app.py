import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile
from streamlit_lottie import st_lottie
import requests

# ✅ Set page configuration
st.set_page_config(page_title="📊 Financial Statement Tool", layout="wide", page_icon="💰")

# 🧭 Load Lottie animation with error handling
def load_lottieurl(url: str):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None

# 🔄 Load animations
upload_animation = load_lottieurl("https://assets4.lottiefiles.com/packages/lf20_jtbfg2nb.json")
process_animation = load_lottieurl("https://assets3.lottiefiles.com/packages/lf20_zrqthn6o.json")
success_animation = load_lottieurl("https://assets3.lottiefiles.com/private_files/lf30_vp9lvfcz.json")

# ✅ Master categorization file URL
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# 🔄 Initialize session state
if "converted_df" not in st.session_state:
    st.session_state["converted_df"] = None
if "auto_categorize" not in st.session_state:
    st.session_state["auto_categorize"] = False
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "📄 PDF to Excel Converter"
if "categorized_files" not in st.session_state:
    st.session_state["categorized_files"] = []

# 🧹 Helper functions
def load_master_file():
    try:
        df = pd.read_excel(MASTER_SHEET_URL)
        df['Key Word'] = df['Key Word'].astype(str).apply(lambda x: re.sub(r'\s+', ' ', x.lower().strip()))
        return df
    except Exception as e:
        st.error(f"⚠️ Error loading master file: {e}")
        return pd.DataFrame()

def extract_wio_transactions(pdf_file):
    transactions = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.strip().split('\n'):
                date_match = re.match(r'(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()
                    ref_number = re.search(r'(P\d{9})', remainder)
                    remainder_clean = remainder.replace(ref_number.group(1), '').strip() if ref_number else remainder
                    numbers = re.findall(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', remainder_clean)
                    if len(numbers) >= 2:
                        amount, running_balance = numbers[-2], numbers[-1]
                        description = remainder_clean.replace(amount, '').replace(running_balance, '').strip()
                    elif len(numbers) == 1:
                        amount, running_balance = numbers[0], ''
                        description = remainder_clean.replace(amount, '').strip()
                    else:
                        continue
                    transactions.append([date, ref_number.group(1) if ref_number else '', description, amount, running_balance])
    return transactions

def categorize_statement(df, master_df):
    df['Categorization'] = df['Description'].apply(
        lambda desc: next((row['Category'] for _, row in master_df.iterrows() if row['Key Word'] in desc.lower()), "Uncategorized")
    )
    return df

def reset_converter():
    st.session_state["converted_df"] = None
    st.session_state["auto_categorize"] = False

def reset_categorization():
    st.session_state["categorized_files"] = []

# -------------------- 🗂️ Sidebar Navigation --------------------
st.sidebar.title("🔎 Navigation")
tab_options = ["📄 PDF to Excel Converter", "📂 Categorization Pilot"]
selected_tab = st.sidebar.radio("", tab_options, index=tab_options.index(st.session_state["active_tab"]))
st.session_state["active_tab"] = selected_tab

# -------------------- 📄 PDF to Excel Converter --------------------
if selected_tab == "📄 PDF to Excel Converter":
    st.title("📝 PDF to Excel Converter")

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_files = st.file_uploader("Upload PDF files:", type=["pdf"], accept_multiple_files=True)
    with col2:
        if st.button("🔄 Reset"):
            reset_converter()
            st.experimental_rerun()

    if uploaded_files:
        all_transactions = []
        with st.spinner("🔍 Extracting transactions..."):
            for file in uploaded_files:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            df = pd.DataFrame(all_transactions, columns=["Date", "Ref. Number", "Description", "Amount", "Running Balance", "Source File"])
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values(by="Date").reset_index(drop=True)

            st.success(f"✅ Extracted {len(df)} transactions!")
            st.dataframe(df, use_container_width=True, height=400)

            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            st.download_button(
                "📥 Download Converted Excel",
                data=excel_buffer,
                file_name="Converted_Statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            if st.button("➡️ Proceed to Categorization"):
                st.session_state["converted_df"] = df
                st.session_state["auto_categorize"] = True
                st.session_state["active_tab"] = "📂 Categorization Pilot"
                st.experimental_rerun()

# -------------------- 📂 Categorization Pilot --------------------
elif selected_tab == "📂 Categorization Pilot":
    st.title("📂 Categorization Pilot")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Reset"):
            reset_categorization()
            st.experimental_rerun()

    master_df = load_master_file()
    if master_df.empty:
        st.error("⚠️ Could not load the master categorization file.")
    else:
        if st.session_state["auto_categorize"] and st.session_state["converted_df"] is not None:
            df_to_categorize = st.session_state["converted_df"]
            categorized_df = categorize_statement(df_to_categorize, master_df)

            st.session_state["categorized_files"].append(("Converted_Categorized_Statement.xlsx", categorized_df))
            st.success("✅ Categorization completed!")

        st.markdown("### 📊 Preview of Categorized Files")
        for file_name, categorized_df in st.session_state["categorized_files"]:
            st.subheader(f"📄 {file_name}")
            st.dataframe(categorized_df.head(10), use_container_width=True)

        st.markdown("### 📂 Upload Additional Files for Categorization")
        uploaded_files = st.file_uploader(
            "Upload Excel/CSV files:",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="manual_upload"
        )

        if uploaded_files:
            for file in uploaded_files:
                try:
                    statement_df = pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
                    categorized_df = categorize_statement(statement_df, master_df)
                    st.session_state["categorized_files"].append((f"Categorized_{file.name}", categorized_df))
                    st.success(f"✅ {file.name} categorized successfully!")
                except Exception as e:
                    st.error(f"⚠️ Error processing {file.name}: {e}")

        if st.session_state["categorized_files"]:
            st.markdown("### 📦 Download All Categorized Files as ZIP")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for file_name, categorized_df in st.session_state["categorized_files"]:
                    file_buffer = io.BytesIO()
                    categorized_df.to_excel(file_buffer, index=False)
                    file_buffer.seek(0)
                    zipf.writestr(file_name, file_buffer.read())

            zip_buffer.seek(0)
            st.download_button(
                label="📥 Download All Categorized Files (ZIP)",
                data=zip_buffer,
                file_name="Categorized_Statements.zip",
                mime="application/zip"
            )
