import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import uuid
import zipfile

# ✅ Master categorization file URL
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# ✅ Set page configuration
st.set_page_config(page_title="Unified App", layout="wide", page_icon="📊")

# 🎨 Custom CSS
st.markdown("""
    <style>
    [data-testid="stToolbar"] { visibility: hidden !important; }
    body { background: linear-gradient(135deg, #141e30, #243b55); color: #e0e0e0; font-size: 12px; }
    .center-title { text-align: center; font-size: 28px; font-weight: 700; margin-bottom: 15px; color: #f1c40f; }
    .watermark { position: fixed; bottom: 5px; left: 0; right: 0; text-align: center; font-size: 11px; color: rgba(200, 200, 200, 0.7); }
    </style>
    <div class="watermark">© 2025 Afsal. All Rights Reserved.</div>
""", unsafe_allow_html=True)

# 🔄 Initialize session state
if "tab" not in st.session_state:
    st.session_state["tab"] = "PDF to Excel Converter"
if "converted_df" not in st.session_state:
    st.session_state["converted_df"] = None
if "auto_categorize" not in st.session_state:
    st.session_state["auto_categorize"] = False

# 🔄 Reset function
def reset_app():
    for key in ["converted_df", "auto_categorize", "tab"]:
        st.session_state.pop(key, None)
    st.experimental_rerun()

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
                    ref_number = re.search(r'(P\\d{9})', remainder)
                    remainder_clean = remainder.replace(ref_number.group(1), '').strip() if ref_number else remainder
                    numbers = re.findall(r'-?\d{1,3}(?:,\\d{3})*(?:\\.\\d{1,2})?', remainder_clean)
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

# 🗂️ Tabs setup
tabs = st.tabs(["📄 PDF to Excel Converter", "📂 Categorization Pilot"])

# -------------------- 📄 PDF to Excel Converter --------------------
with tabs[0]:
    if st.session_state["tab"] == "PDF to Excel Converter":
        st.header("📄 PDF to Excel Converter")
        uploaded_files = st.file_uploader("📤 Upload PDF files", type=["pdf"], accept_multiple_files=True)

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

                st.success("✅ Transactions extracted successfully!")
                st.dataframe(df, use_container_width=True)

                # ✅ Download converted Excel
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False)
                excel_buffer.seek(0)
                st.download_button(
                    "📥 Download Converted Excel",
                    data=excel_buffer,
                    file_name="Converted_Statement.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # Store converted data for categorization
                if st.button("➡️ Categorize Converted Statement"):
                    st.session_state["converted_df"] = df
                    st.session_state["auto_categorize"] = True
                    st.session_state["tab"] = "Categorization Pilot"
                    st.experimental_rerun()

# -------------------- 📂 Categorization Pilot --------------------
with tabs[1]:
    if st.session_state["tab"] == "Categorization Pilot":
        st.header("📂 Categorization Pilot")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 Reset"):
                reset_app()

        master_df = load_master_file()
        if master_df.empty:
            st.error("⚠️ Could not load the master file.")
        else:
            # ✅ Auto-categorization from converted statement
            if st.session_state["auto_categorize"] and st.session_state["converted_df"] is not None:
                df_to_categorize = st.session_state["converted_df"]
                st.success("✅ Auto-categorizing converted statement...")
                categorized_df = categorize_statement(df_to_categorize, master_df)
                st.dataframe(categorized_df, use_container_width=True)

                # Download categorized file
                buffer = io.BytesIO()
                categorized_df.to_excel(buffer, index=False)
                buffer.seek(0)
                st.download_button(
                    "📥 Download Categorized Excel",
                    data=buffer,
                    file_name="Categorized_Statement.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # Reset auto-categorize flag
                st.session_state["auto_categorize"] = False

            else:
                st.markdown("### 📂 Upload files for independent categorization:")
                uploaded_files = st.file_uploader(
                    "📤 Upload Statement Files (Excel or CSV)",
                    type=["xlsx", "csv"],
                    accept_multiple_files=True
                )

                if uploaded_files:
                    for file in uploaded_files:
                        st.subheader(f"📄 {file.name}")
                        try:
                            statement_df = pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
                            st.dataframe(statement_df.head(), use_container_width=True)
                            categorized_df = categorize_statement(statement_df, master_df)
                            st.success(f"✅ {file.name} categorized successfully!")
                            st.dataframe(categorized_df.head(), use_container_width=True)

                            # Download categorized file
                            buffer = io.BytesIO()
                            categorized_df.to_excel(buffer, index=False)
                            buffer.seek(0)
                            st.download_button(
                                label=f"📥 Download {file.name}",
                                data=buffer,
                                file_name=f"Categorized_{file.name}",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except Exception as e:
                            st.error(f"⚠️ Error processing {file.name}: {e}")
                else:
                    st.info("👆 Upload files or use the **PDF to Excel Converter** for automatic categorization.")
