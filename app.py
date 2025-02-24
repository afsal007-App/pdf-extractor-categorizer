import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
import uuid
import zipfile

# ✅ Master categorization file URL
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# ✅ Set page configuration FIRST
st.set_page_config(
    page_title="Unified App",
    layout="wide",
    page_icon="📊"
)

# 🎨 Custom CSS for styling
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
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = str(uuid.uuid4())

# 🔄 Reset function
def reset_app():
    st.session_state["uploader_key"] = str(uuid.uuid4())
    st.session_state.pop("converted_df", None)
    st.session_state.pop("proceed_to_categorization", None)
    st.rerun()

# 🧹 Helper functions
def load_master_file():
    try:
        df = pd.read_excel(MASTER_SHEET_URL)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f'⚠️ Error loading master file: {e}')
        return pd.DataFrame()

def clean_text(text):
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

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

# 🗂️ Tabs setup
tab1, tab2 = st.tabs(["📄 PDF to Excel Converter", "📂 Categorization Pilot"])

# -------------------- 📄 PDF to Excel Converter --------------------
with tab1:
    st.header("PDF to Excel Converter")

    st.write(
        "Upload PDF statements to get a consolidated Excel with:\n"
        "- Extracted running balance from the statement.\n"
        "- A newly calculated balance column.\n"
        "- Bank-specific extraction logic.\n"
    )

    bank_options = ["Wio Bank", "Other Bank (Coming Soon)"]
    selected_bank = st.selectbox("🏦 Select Bank:", bank_options)

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
                        ref_number_match = re.search(r'(P\d{9})', remainder)
                        ref_number = ref_number_match.group(1) if ref_number_match else ''
                        remainder_clean = remainder.replace(ref_number, '').strip() if ref_number else remainder
                        numbers = re.findall(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', remainder_clean)
                        if len(numbers) >= 2:
                            amount, running_balance = numbers[-2], numbers[-1]
                            description = remainder_clean.replace(amount, '').replace(running_balance, '').strip()
                        elif len(numbers) == 1:
                            amount = numbers[0]
                            running_balance = ''
                            description = remainder_clean.replace(amount, '').strip()
                        else:
                            continue
                        transactions.append([date, ref_number, description, amount, running_balance])
        return transactions

    uploaded_files = st.file_uploader("📤 Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        all_transactions = []
        with st.spinner('🔍 Extracting transactions...'):
            for file in uploaded_files:
                transactions = extract_wio_transactions(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ['Date', 'Ref. Number', 'Description', 'Amount (Incl. VAT)', 'Running Balance (Extracted)', 'Source File']
            df = pd.DataFrame(all_transactions, columns=columns)
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
            df["Amount (Incl. VAT)"] = df["Amount (Incl. VAT)"].replace({",": ""}, regex=True).astype(float)
            df["Running Balance (Extracted)"] = pd.to_numeric(df["Running Balance (Extracted)"].replace({",": ""}, regex=True), errors="coerce")
            df = df.dropna(subset=['Date']).sort_values(by='Date').reset_index(drop=True)

            st.success("✅ Transactions extracted successfully!")
            st.dataframe(df, use_container_width=True)

            # ✅ Add download button for converted Excel
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            st.download_button(
                label="📥 Download Converted Excel",
                data=excel_buffer,
                file_name="Converted_Statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.session_state["converted_df"] = df
            proceed = st.checkbox('➡️ Proceed to Categorization')
            if proceed:
                st.session_state["proceed_to_categorization"] = True
                st.success("✅ Switch to the 'Categorization Pilot' tab to continue.")

# -------------------- 📂 Categorization Pilot --------------------
with tab2:
    st.markdown('<h1 class="center-title">🤖 Categorization Bot</h1>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 Reset"):
            reset_app()

    master_df = load_master_file()

    if master_df.empty:
        st.error("⚠️ Could not load the master file.")
    else:
        df_to_categorize = None

        if st.session_state.get("converted_df") is not None and st.session_state.get("proceed_to_categorization"):
            st.success("✅ Using converted data from PDF to Excel Converter.")
            df_to_categorize = st.session_state["converted_df"]
        else:
            uploaded_files = st.file_uploader(
                "📂 Upload Statement Files (Excel or CSV)",
                type=["xlsx", "csv"],
                accept_multiple_files=True,
                key=st.session_state["uploader_key"]
            )

            if uploaded_files:
                categorized_files = []
                for file in uploaded_files:
                    try:
                        statement_df = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
                        desc_col = find_description_column(statement_df.columns)
                        if desc_col:
                            categorized = categorize_statement(statement_df, master_df, desc_col)
                            st.success(f"✅ {file.name} categorized successfully!")
                            st.dataframe(categorized.head(), use_container_width=True)

                            buffer = io.BytesIO()
                            categorized.to_excel(buffer, index=False)
                            buffer.seek(0)
                            categorized_files.append((file.name, buffer))

                            st.download_button(
                                label=f"📥 Download {file.name}",
                                data=buffer,
                                file_name=f"Categorized_{file.name}",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.error(f"⚠️ No description column found in {file.name}.")
                    except Exception as e:
                        st.error(f"⚠️ Error processing {file.name}: {e}")

                if categorized_files:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                        for fname, data in categorized_files:
                            zipf.writestr(f"Categorized_{fname}", data.getvalue())
                    zip_buffer.seek(0)
                    st.download_button(
                        label="📦 Download All Categorized Files as ZIP",
                        data=zip_buffer,
                        file_name="Categorized_Files.zip",
                        mime="application/zip"
                    )
            else:
                st.info("👆 Upload files to begin.")
