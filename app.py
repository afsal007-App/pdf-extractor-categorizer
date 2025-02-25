import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile
from streamlit_lottie import st_lottie
import requests

# ✅ Set page configuration
st.set_page_config(page_title="📊 Financial Statement Tool", layout="wide", page_icon="💵")

# 🎨 Define color palette and styling
PRIMARY_COLOR = "#2C3E50"
SECONDARY_COLOR = "#ECF0F1"
ACCENT_COLOR = "#3498DB"
WARNING_COLOR = "#E74C3C"
SUCCESS_COLOR = "#27AE60"
TEXT_COLOR = "#2C3E50"

st.markdown(f"""
    <style>
        .stButton > button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            padding: 12px 20px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            width: 100%;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .stButton > button:hover {{
            background-color: {ACCENT_COLOR};
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: {TEXT_COLOR};
        }}
        .reportview-container .main .block-container {{
            padding: 1rem 2rem;
            background-color: {SECONDARY_COLOR};
            border-radius: 10px;
        }}
        .css-1q8dd3e {{
            font-size: 16px;
        }}
    </style>
""", unsafe_allow_html=True)

# ✅ Load Lottie animation with error handling
def load_lottieurl(url: str):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None

# 🔄 Load animations
upload_animation = load_lottieurl("https://assets7.lottiefiles.com/packages/lf20_jcikwtux.json")
success_animation = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_dyvyz7.json")
reset_animation = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_twijbubv.json")

# ✅ Master categorization file URL
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# 🔄 Initialize session state
def initialize_session_state():
    if "converted_df" not in st.session_state:
        st.session_state["converted_df"] = None
    if "auto_categorize" not in st.session_state:
        st.session_state["auto_categorize"] = False
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "PDF to Excel Converter"
    if "categorized_files" not in st.session_state:
        st.session_state["categorized_files"] = {}
    if "uploaded_files" not in st.session_state:
        st.session_state["uploaded_files"] = []
initialize_session_state()

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
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = text.strip().split('\n')
            for line_num, line in enumerate(lines):
                date_match = re.match(r'(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    date = date_match.group(1)
                    remainder = line[len(date):].strip()

                    ref_number_match = re.search(r'(?:Ref(?:erence)? Number[:\s]*)?(\w+)', remainder)
                    ref_number = ref_number_match.group(1) if ref_number_match else ""

                    numbers = re.findall(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', remainder)
                    amount = float(numbers[-2].replace(',', '')) if len(numbers) >= 2 else 0.0
                    balance = float(numbers[-1].replace(',', '')) if len(numbers) >= 1 else 0.0

                    description = re.sub(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', '', remainder).replace(ref_number, '').strip()

                    transactions.append([date, ref_number, description, amount, balance])

    return transactions

def calculate_calculated_balance(df):
    if "Amount (Incl. VAT)" in df.columns:
        df = df.sort_values(by="Date")
        df['Calculated Balance'] = df['Amount (Incl. VAT)'].cumsum()
    else:
        st.error("⚠️ 'Amount (Incl. VAT)' column is missing. Please check the extracted data.")
    return df

def categorize_statement(df, master_df):
    df['Categorization'] = df['Description'].apply(
        lambda desc: next((row['Category'] for _, row in master_df.iterrows() if row['Key Word'] in desc.lower()), "Uncategorized")
    )
    return df

def reset_converter_section():
    st.session_state["converted_df"] = None
    st.session_state["uploaded_files"] = []
    st.session_state["auto_categorize"] = False
    st.success("✅ PDF to Excel Converter section has been reset.")

def reset_categorization_section():
    st.session_state["categorized_files"] = {}
    st.success("✅ Categorization section has been reset.")

# -------------------- 🗂️ Vertical Sidebar with Buttons --------------------
st.sidebar.title("🚀 Navigation")

nav_options = {
    "PDF to Excel Converter": "📝 PDF to Excel Converter",
    "Categorization Pilot": "📂 Categorization Pilot"
}

for page, label in nav_options.items():
    if st.sidebar.button(label, key=page, use_container_width=True):
        st.session_state["active_tab"] = page
        st.rerun()

# -------------------- 📄 PDF to Excel Converter --------------------
if st.session_state["active_tab"] == "PDF to Excel Converter":
    st.header("📝 PDF to Excel Converter")

    col1, col2 = st.columns([3, 1])
    with col1:
        if upload_animation:
            st_lottie(upload_animation, height=150, key="upload")
        uploaded_files = st.file_uploader("Upload PDF files:", type=["pdf"], accept_multiple_files=True)

    with col2:
        st.subheader("⚙️ Options")
        if st.button("♻️ Reset Converter Section"):
            reset_converter_section()
            st.experimental_rerun()

    if uploaded_files:
        st.session_state["uploaded_files"] = uploaded_files
        all_transactions = []
        with st.spinner("🔍 Extracting transactions..."):
            for file in uploaded_files:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            df = pd.DataFrame(all_transactions, columns=["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Balance (AED)", "Source File"])
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
            df = calculate_calculated_balance(df)

            st.session_state["converted_df"] = df
            st.success(f"✅ Extracted {len(df)} transactions with calculated balances!")
            st.dataframe(df, use_container_width=True, height=400)

            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)

            st.download_button(
                "📥 Download Converted Excel",
                data=buffer,
                file_name="Converted_Statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            if st.button("➡️ Proceed to Categorization"):
                st.session_state["auto_categorize"] = True
                st.session_state["active_tab"] = "Categorization Pilot"
                st.experimental_rerun()

# -------------------- 📂 Categorization Pilot --------------------
elif st.session_state["active_tab"] == "Categorization Pilot":
    st.header("📂 Categorization Pilot")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("♻️ Reset Categorization Section"):
            reset_categorization_section()
            st.experimental_rerun()

    master_df = load_master_file()
    if master_df.empty:
        st.error("⚠️ Could not load the master categorization file.")
    else:
        if st.session_state["auto_categorize"] and st.session_state["converted_df"] is not None:
            df_to_categorize = st.session_state["converted_df"]
            categorized_df = categorize_statement(df_to_categorize, master_df)

            st.session_state["categorized_files"]["Converted_Categorized_Statement.xlsx"] = categorized_df
            st.success("✅ Categorization completed!")
            if success_animation:
                st_lottie(success_animation, height=120, key="success")

        st.markdown("### 📊 Preview of Categorized Files")
        if st.session_state["categorized_files"]:
            for file_name, categorized_df in st.session_state["categorized_files"].items():
                st.subheader(f"📄 {file_name}")
                st.dataframe(categorized_df.head(10), use_container_width=True)
        else:
            st.info("👆 No categorized files available. Upload or convert files to categorize.")

        st.markdown("### 📂 Upload Additional Files for Categorization")
        uploaded_files = st.file_uploader(
            "Upload Excel/CSV files:",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="manual_upload"
        )

        if uploaded_files:
            for file in uploaded_files:
                if f"Categorized_{file.name}" in st.session_state["categorized_files"]:
                    st.warning(f"⚠️ {file.name} has already been categorized. Skipping duplicate.")
                    continue
                try:
                    statement_df = pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
                    statement_df = statement_df[[col for col in statement_df.columns if col in ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Balance (AED)"]]]
                    statement_df = calculate_calculated_balance(statement_df)
                    categorized_df = categorize_statement(statement_df, master_df)
                    st.session_state["categorized_files"][f"Categorized_{file.name}"] = categorized_df
                    st.success(f"✅ {file.name} categorized successfully!")
                except Exception as e:
                    st.error(f"⚠️ Error processing {file.name}: {e}")

        if st.session_state["categorized_files"]:
            st.markdown("### 📦 Download All Categorized Files as ZIP")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for file_name, categorized_df in st.session_state["categorized_files"].items():
                    buffer = io.BytesIO()
                    categorized_df.to_excel(buffer, index=False)
                    buffer.seek(0)
                    zipf.writestr(file_name, buffer.read())

            zip_buffer.seek(0)
            st.download_button(
                label="📥 Download All Categorized Files as ZIP",
                data=zip_buffer,
                file_name="Categorized_Statements.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.info("👆 No files to download. Upload or convert files to see download options.")
