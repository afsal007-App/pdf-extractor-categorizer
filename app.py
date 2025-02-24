
import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

# ✅ Set page configuration FIRST
st.set_page_config(
    page_title="Unified App",
    layout="wide",
    page_icon="📊"
)

st.title("Unified Application")

tab1, tab2 = st.tabs(["📄 PDF to Excel Converter", "📂 Categorization Pilot"])

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
                        ref_number = ref_number_match.group(1) if ref_number_match else ""
                        remainder_clean = remainder.replace(ref_number, "").strip() if ref_number else remainder
                        numbers = re.findall(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', remainder_clean)
                        if len(numbers) >= 2:
                            amount, running_balance = numbers[-2], numbers[-1]
                            description = remainder_clean.replace(amount, "").replace(running_balance, "").strip()
                        elif len(numbers) == 1:
                            amount = numbers[0]
                            running_balance = ""
                            description = remainder_clean.replace(amount, "").strip()
                        else:
                            continue
                        transactions.append([date, ref_number, description, amount, running_balance])
        return transactions

    def extract_other_bank_transactions(pdf_file):
        st.warning("🚧 Extraction logic for this bank is under development.")
        return []

    extraction_functions = {
        "Wio Bank": extract_wio_transactions,
        "Other Bank (Coming Soon)": extract_other_bank_transactions,
    }

    uploaded_files = st.file_uploader("📤 Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        all_transactions = []
        with st.spinner("🔍 Extracting transactions..."):
            extraction_function = extraction_functions.get(selected_bank)
            for file in uploaded_files:
                transactions = extraction_function(file)
                for transaction in transactions:
                    transaction.append(file.name)  # Add source file name
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
            df = pd.DataFrame(all_transactions, columns=columns)
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors='coerce')
            df["Amount (Incl. VAT)"] = df["Amount (Incl. VAT)"].replace({',': ''}, regex=True).astype(float)
            df["Running Balance (Extracted)"] = pd.to_numeric(
                df["Running Balance (Extracted)"].replace({',': ''}, regex=True), errors='coerce'
            )
            df = df.dropna(subset=["Date"]).sort_values(by="Date").reset_index(drop=True)
            opening_balance = st.number_input("💰 Enter Opening Balance:", value=0.0, step=0.01)
            df["Calculated Balance"] = opening_balance + df["Amount (Incl. VAT)"].cumsum()

            st.success("✅ Transactions extracted with running and calculated balances!")
            st.dataframe(df, use_container_width=True)
            st.write(f"🔢 **Total Transactions:** {len(df)}")

            output = io.BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)

            st.download_button(
                label="📥 Download Consolidated Excel (With Balances)",
                data=output,
                file_name="consolidated_transactions_with_balances.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning("⚠️ No transactions found. Please check the PDF format or selected bank.")

with tab2:
    st.header("Categorization Pilot")


# 🚀 Integrated Categorization Code
    import streamlit as st
    import pandas as pd
    import re
    from io import BytesIO
    import zipfile
    import uuid
    
    # ✅ Master categorization file URL
    MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"
    
    # 🎨 Updated CSS for improved design and hiding the GitHub icon
    st.markdown("""
        <style>
        [data-testid="stToolbar"] {
            visibility: hidden !important;
        }
    
        body {
            background: linear-gradient(135deg, #141e30, #243b55);
            color: #e0e0e0;
            font-size: 12px;
        }
    
        .center-title {
            text-align: center;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 15px;
            color: #f1c40f;
            text-shadow: 2px 2px 5px rgba(0,0,0,0.4);
            animation: fadeIn 1s ease-in-out;
        }
    
        h2, h3, .stSubheader {
            font-size: 16px !important;
            font-weight: 600;
            margin-bottom: 10px;
            color: #f39c12;
            animation: slideIn 0.7s ease forwards;
        }
    
        .stDataFrame {
            background-color: rgba(255, 255, 255, 0.07);
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            animation: fadeInUp 0.5s ease;
        }
    
        .stButton button, .stDownloadButton button {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            font-weight: bold;
            border-radius: 25px;
            padding: 6px 16px;
            font-size: 11px;
            width: 100%;
            transition: all 0.3s ease;
        }
    
        .stButton button:hover, .stDownloadButton button:hover {
            background: linear-gradient(135deg, #2ecc71, #27ae60);
            transform: scale(1.05);
            box-shadow: 0 0 10px rgba(46, 204, 113, 0.7);
        }
    
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
    
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    
        .watermark {
            position: fixed;
            bottom: 5px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 11px;
            font-style: italic;
            color: rgba(200, 200, 200, 0.7);
            pointer-events: none;
            animation: fadeIn 2s ease;
        }
        </style>
    
        <div class="watermark">© 2025 Afsal. All Rights Reserved.</div>
    """, unsafe_allow_html=True)
    
    # ✅ Initialize session state variables
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = str(uuid.uuid4())  # Unique key for file uploader
    
    # 🔄 Reset Function
    def reset_app():
        """Resets the session state and clears uploaded files."""
        st.session_state["uploader_key"] = str(uuid.uuid4())  # Generate new key to reset uploader
        st.rerun()
    
    def load_master_file():
        """Load and clean the master categorization file."""
        try:
            df = pd.read_excel(MASTER_SHEET_URL)
            df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
            return df
        except Exception as e:
            st.error(f"⚠️ Error loading master file: {e}")
            return pd.DataFrame()
    
    def clean_text(text):
        """Standardize text for matching."""
        return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()
    
    def find_description_column(columns):
        """Identify the description column."""
        possible = ['description', 'details', 'narration', 'particulars', 'transaction details', 'remarks']
        return next((col for col in columns if any(name in col.lower() for name in possible)), None)
    
    def categorize_description(description, master_df):
        """Assign categories based on keywords."""
        cleaned = clean_text(description)
        for _, row in master_df.iterrows():
            if row['Key Word'] and row['Key Word'] in cleaned:
                return row['Category']
        return 'Uncategorized'
    
    def categorize_statement(statement_df, master_df, desc_col):
        """Categorize the entire statement."""
        statement_df['Categorization'] = statement_df[desc_col].apply(lambda x: categorize_description(x, master_df))
        return statement_df
    
    # 🌐 Main Interface
    st.markdown('<h1 class="center-title">🤖 Categorization Bot</h1>', unsafe_allow_html=True)
    
    # 🔄 Reset Button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 Reset"):
            reset_app()
    
    # 📂 File Upload with dynamic key to reset uploader
    uploaded_files = st.file_uploader(
        "📂 Upload Statement Files (Excel or CSV)",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
        key=st.session_state["uploader_key"]
    )
    
    if uploaded_files:
        with st.spinner('🚀 Loading master file...'):
            master_df = load_master_file()
    
        if master_df.empty:
            st.error("⚠️ Could not load the master file.")
        else:
            categorized_files = []
            st.markdown('## 📑 Uploaded Files Preview & Results')
    
            for file in uploaded_files:
                st.subheader(f"📄 {file.name}")
                try:
                    statement_df = pd.read_excel(file)
                except Exception:
                    statement_df = pd.read_csv(file)
    
                st.dataframe(statement_df.head(), use_container_width=True)
                desc_col = find_description_column(statement_df.columns)
    
                if desc_col:
                    categorized = categorize_statement(statement_df, master_df, desc_col)
                    st.success(f"✅ {file.name} categorized successfully!")
                    st.dataframe(categorized.head(), use_container_width=True)
    
                    buffer = BytesIO()
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
    
            # 📦 Download All as ZIP
            if categorized_files:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zipf:
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
