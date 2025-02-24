import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# ✅ Master categorization file URL
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1I_Fz3slHP1mnfsKKgAFl54tKvqlo65Ug/export?format=xlsx"

# ✅ Set page configuration
st.set_page_config(page_title="Unified App", layout="wide", page_icon="📊")

# 🔄 Initialize session state
if "converted_df" not in st.session_state:
    st.session_state["converted_df"] = None
if "auto_categorize" not in st.session_state:
    st.session_state["auto_categorize"] = False

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

# -------------------- 🗂️ Tabs --------------------
tab_labels = ["📄 PDF to Excel Converter", "📂 Categorization Pilot"]
tabs = st.tabs(tab_labels)

# -------------------- 📄 PDF to Excel Converter --------------------
with tabs[0]:
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

            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            st.download_button(
                "📥 Download Converted Excel",
                data=excel_buffer,
                file_name="Converted_Statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            if st.button("➡️ Categorize Converted Statement"):
                st.session_state["converted_df"] = df
                st.session_state["auto_categorize"] = True
                st.rerun()

# -------------------- 📂 Categorization Pilot --------------------
with tabs[1]:
    st.header("📂 Categorization Pilot")

    master_df = load_master_file()
    if master_df.empty:
        st.error("⚠️ Could not load the master file.")
    else:
        if st.session_state["auto_categorize"] and st.session_state["converted_df"] is not None:
            st.success("✅ Auto-categorizing converted statement...")
            df_to_categorize = st.session_state["converted_df"]
            categorized_df = categorize_statement(df_to_categorize, master_df)
            st.dataframe(categorized_df, use_container_width=True)

            buffer = io.BytesIO()
            categorized_df.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                "📥 Download Categorized Excel",
                data=buffer,
                file_name="Categorized_Statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.session_state["auto_categorize"] = False

        st.markdown("### 📂 Or upload files manually for categorization:")
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
        elif not st.session_state["auto_categorize"]:
            st.info("👆 Upload files or use the **PDF to Excel Converter** to auto-categorize converted statements.")
