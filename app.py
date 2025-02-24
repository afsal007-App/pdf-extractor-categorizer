
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
                            description = re.sub(rf'\\s*{re.escape(amount)}\\s*{re.escape(running_balance)}$', '', remainder_clean).strip()
                        elif len(numbers) == 1:
                            amount = numbers[0]
                            running_balance = ""
                            description = re.sub(rf'\\s*{re.escape(amount)}$', '', remainder_clean).strip()
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
    st.write("🚧 Placeholder for Categorization Pilot functionality.")
