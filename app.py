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

# 🎨 Define color palette and styling
PRIMARY_COLOR = "#4A90E2"
SECONDARY_COLOR = "#F5F7FA"
ACCENT_COLOR = "#50E3C2"
TEXT_COLOR = "#333333"

st.markdown(f"""
    <style>
        .stButton > button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            padding: 10px 16px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            width: 100%;
            border: none;
            cursor: pointer;
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
upload_animation = load_lottieurl("https://assets1.lottiefiles.com/packages/lf20_puciaact.json")
process_animation = load_lottieurl("https://assets6.lottiefiles.com/private_files/lf30_6xiyzbtp.json")
success_animation = load_lottieurl("https://assets7.lottiefiles.com/packages/lf20_4kgj19pg.json")
reset_animation = load_lottieurl("https://assets2.lottiefiles.com/packages/lf20_ovvdxqph.json")

# ✅ Master categorization file URL
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# 🔄 Initialize session state
if "converted_df" not in st.session_state:
    st.session_state["converted_df"] = None
if "auto_categorize" not in st.session_state:
    st.session_state["auto_categorize"] = False
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "PDF to Excel Converter"
if "categorized_files" not in st.session_state:
    st.session_state["categorized_files"] = {}
if "processed_files" not in st.session_state:
    st.session_state["processed_files"] = set()

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
                    description = remainder
                    numbers = re.findall(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', remainder)
                    amount = numbers[-1] if numbers else ''
                    transactions.append([date, description, amount])
    return transactions

def categorize_statement(df, master_df):
    df['Categorization'] = df['Description'].apply(
        lambda desc: next((row['Category'] for _, row in master_df.iterrows() if row['Key Word'] in desc.lower()), "Uncategorized")
    )
    return df

def remove_duplicates(df):
    return df.drop_duplicates(subset=["Date", "Description", "Amount"])

def reset_converter_section():
    st.session_state["converted_df"] = None
    st.session_state["auto_categorize"] = False
    st.session_state["processed_files"] = set()
    st.success("✅ PDF to Excel Converter section has been reset.")

def reset_categorization_section():
    st.session_state["categorized_files"] = {}
    st.session_state["processed_files"] = set()
    st.success("✅ Categorization section has been reset.")

# -------------------- 🗂️ Vertical Sidebar with Buttons --------------------
st.sidebar.title("🚀 Navigation")

nav_options = {
    "PDF to Excel Converter": "📝 PDF to Excel Converter",
    "Categorization Pilot": "📂 Categorization Pilot"
}

for page, label in nav_options.items():
    if st.sidebar.button(label, key=page, help=f"Navigate to {label}", use_container_width=True):
        st.session_state["active_tab"] = page
        st.rerun()

# -------------------- 📄 PDF to Excel Converter --------------------
if st.session_state["active_tab"] == "PDF to Excel Converter":
    st.header("PDF to Excel Converter", divider='rainbow')

    col1, col2 = st.columns([3, 1])
    with col1:
        if upload_animation:
            st_lottie(upload_animation, height=180, key="upload")
        uploaded_files = st.file_uploader("Upload PDF files:", type=["pdf"], accept_multiple_files=True)

    with col2:
        st.subheader("⚙️ Options")
        if st.button("♻️ Reset Converter Section"):
            reset_converter_section()
            st.rerun()

    if uploaded_files:
        all_transactions = []
        with st.spinner("🔍 Extracting transactions..."):
            for file in uploaded_files:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            df = pd.DataFrame(all_transactions, columns=["Date", "Description", "Amount", "Source File"])
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values(by="Date").reset_index(drop=True)
            df = remove_duplicates(df)

            st.success(f"✅ Extracted {len(df)} unique transactions!")
            st.dataframe(df, use_container_width=True, height=400)

            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            st.download_button(
                "📥 Download Converted Excel",
                data=excel_buffer,
                file_name="Converted_Statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            if st.button("➡️ Proceed to Categorization"):
                st.session_state["converted_df"] = df
                st.session_state["auto_categorize"] = True
                st.session_state["active_tab"] = "Categorization Pilot"
                st.rerun()

# -------------------- 📂 Categorization Pilot --------------------
elif st.session_state["active_tab"] == "Categorization Pilot":
    st.header("Categorization Pilot", divider='rainbow')

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("♻️ Reset Categorization Section"):
            reset_categorization_section()
            st.rerun()

    master_df = load_master_file()
    if master_df.empty:
        st.error("⚠️ Could not load the master categorization file.")
    else:
        if st.session_state["auto_categorize"] and st.session_state["converted_df"] is not None:
            df_to_categorize = st.session_state["converted_df"]
            categorized_df = categorize_statement(df_to_categorize, master_df)
            categorized_df = remove_duplicates(categorized_df)

            file_name = "Converted_Categorized_Statement.xlsx"
            st.session_state["categorized_files"][file_name] = categorized_df
            st.success("✅ Categorization completed!")
            if success_animation:
                st_lottie(success_animation, height=150, key="success")

        st.markdown("### 📊 Preview of Categorized Files")
        if st.session_state["categorized_files"]:
            for file_name, categorized_df in st.session_state["categorized_files"].items():
                st.subheader(f"📄 {file_name}")
                st.dataframe(remove_duplicates(categorized_df).head(10), use_container_width=True)
        else:
            st.info("👆 No categorized files to preview. Upload or convert files to see them here.")

        st.markdown("### 📂 Upload Additional Files for Categorization")
        uploaded_files = st.file_uploader(
            "Upload Excel/CSV files:",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="manual_upload"
        )

        if uploaded_files:
            for file in uploaded_files:
                if file.name in st.session_state["categorized_files"]:
                    st.warning(f"⚠️ {file.name} has already been categorized and previewed. Skipping duplicate.")
                    continue
                try:
                    statement_df = pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
                    statement_df = statement_df[[col for col in statement_df.columns if col in ["Date", "Description", "Amount"]]]

                    categorized_df = categorize_statement(statement_df, master_df)
                    categorized_df = remove_duplicates(categorized_df)

                    st.session_state["categorized_files"][f"Categorized_{file.name}"] = categorized_df
                    st.success(f"✅ {file.name} categorized successfully!")
                except Exception as e:
                    st.error(f"⚠️ Error processing {file.name}: {e}")

        if st.session_state["categorized_files"]:
            st.markdown("### 📦 Download All Categorized Files as ZIP")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for file_name, categorized_df in st.session_state["categorized_files"].items():
                    unique_df = remove_duplicates(categorized_df)
                    file_buffer = io.BytesIO()
                    unique_df.to_excel(file_buffer, index=False)
                    file_buffer.seek(0)
                    zipf.writestr(file_name, file_buffer.read())

            zip_buffer.seek(0)
            st.download_button(
                label="📥 Download All Categorized Files (ZIP)",
                data=zip_buffer,
                file_name="Categorized_Statements.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.info("👆 No files to download. Please upload or convert files first.")
