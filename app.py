
---

### 🖥️ **Step 3: Create `app.py`** *(Main Application Code)*

```python
import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

# ✅ Master categorization file URL (replace with your Google Sheet link)
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# 🌟 Page Configuration
st.set_page_config(page_title="📄 Extract & Categorize Statements", layout="wide")

# 🏷️ App Title
st.title("📄 PDF Extractor & 📊 Transaction Categorizer")

# 🚀 Utility Functions
def clean_text(text):
    """Standardize text for keyword matching."""
    return re.sub(r'\s+', ' ', str(text).lower().replace('–', '-').replace('—', '-')).strip()

def load_master_file():
    """Load master categorization file."""
    try:
        df = pd.read_excel(MASTER_SHEET_URL)
        df['Key Word'] = df['Key Word'].astype(str).apply(clean_text)
        return df
    except Exception as e:
        st.error(f"⚠️ Error loading master file: {e}")
        return pd.DataFrame()

def find_description_column(columns):
    """Identify the description column."""
    possible_names = ['description', 'details', 'narration', 'particulars', 'transaction details', 'remarks']
    return next((col for col in columns if any(name in col.lower() for name in possible_names)), None)

def categorize_description(description, master_df):
    """Assign category based on keywords."""
    cleaned = clean_text(description)
    for _, row in master_df.iterrows():
        if row['Key Word'] and row['Key Word'] in cleaned:
            return row['Category']
    return 'Uncategorized'

def categorize_statement(df, master_df, desc_col):
    """Categorize all transactions."""
    df['Categorization'] = df[desc_col].apply(lambda x: categorize_description(x, master_df))
    return df

def extract_transactions_from_pdf(pdf_file):
    """Extract transactions from PDFs (Wio Bank format example)."""
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
                    ref_match = re.search(r'(P\d{9})', remainder)
                    ref_number = ref_match.group(1) if ref_match else ""
                    remainder_clean = remainder.replace(ref_number, "").strip()
                    numbers = re.findall(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?', remainder_clean)

                    if len(numbers) >= 2:
                        amount, running_balance = numbers[-2], numbers[-1]
                        description = remainder_clean.replace(amount, "").replace(running_balance, "").strip()
                    elif len(numbers) == 1:
                        amount, running_balance = numbers[0], ""
                        description = remainder_clean.replace(amount, "").strip()
                    else:
                        continue

                    transactions.append([date, ref_number, description, amount, running_balance])
    return transactions

# 🗂️ Create tabs
tab1, tab2 = st.tabs(["📄 Extract Statements", "📊 Categorize Transactions"])

# 🌟 Tab 1: Extract Statements
with tab1:
    st.subheader("Step 1: Upload & Extract PDF Statements")

    uploaded_files = st.file_uploader("📤 Upload PDF files", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        all_transactions = []
        with st.spinner("🔍 Extracting transactions..."):
            for file in uploaded_files:
                transactions = extract_transactions_from_pdf(file)
                for transaction in transactions:
                    transaction.append(file.name)
                all_transactions.extend(transactions)

        if all_transactions:
            columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
            extracted_df = pd.DataFrame(all_transactions, columns=columns)
            extracted_df["Date"] = pd.to_datetime(extracted_df["Date"], format="%d/%m/%Y", errors='coerce')
            extracted_df["Amount (Incl. VAT)"] = extracted_df["Amount (Incl. VAT)"].replace({',': ''}, regex=True).astype(float)

            st.session_state["extracted_df"] = extracted_df  # Save to session state

            st.success("✅ Transactions extracted!")
            st.dataframe(extracted_df, use_container_width=True)
            st.write(f"🔢 **Total Transactions:** {len(extracted_df)}")
        else:
            st.warning("⚠️ No transactions found. Check your PDF format.")

# 🌟 Tab 2: Categorize Transactions
with tab2:
    st.subheader("Step 2: Categorize Extracted Transactions")

    if "extracted_df" in st.session_state:
        extracted_df = st.session_state["extracted_df"]

        with st.spinner('🚀 Loading categorization rules...'):
            master_df = load_master_file()

        if not master_df.empty:
            desc_col = find_description_column(extracted_df.columns)
            if desc_col:
                categorized_df = categorize_statement(extracted_df.copy(), master_df, desc_col)
                st.success("✅ Transactions categorized!")
                st.dataframe(categorized_df, use_container_width=True)
                st.write(f"🔢 **Total Categorized Transactions:** {len(categorized_df)}")

                # Download button
                output = io.BytesIO()
                categorized_df.to_excel(output, index=False)
                output.seek(0)
                st.download_button(
                    label="📥 Download Categorized Transactions",
                    data=output,
                    file_name="categorized_transactions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("⚠️ No description column found.")
        else:
            st.error("⚠️ Could not load the master categorization file.")
    else:
        st.warning("⚠️ Extract statements first in the 'Extract Statements' tab.")
