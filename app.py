import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

# Streamlit page setup
st.set_page_config(page_title="📄 PDF to Excel Converter & Categorizer", layout="centered")

st.title("📄 PDF to Excel Converter & Categorizer")
st.write(
    "Upload PDF statements to get a consolidated Excel with:\n"
    "- Extracted running balance.\n"
    "- Newly calculated balance column.\n"
    "- Bank-specific extraction logic.\n"
    "- Option to categorize transactions."
)

# ✅ Bank selection
bank_options = ["Wio Bank", "Other Bank (Coming Soon)"]
selected_bank = st.selectbox("🏦 Select Bank:", bank_options)

# ✅ Extraction functions
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

def extract_other_bank_transactions(pdf_file):
    st.warning("🚧 Extraction logic for this bank is under development.")
    return []

# ✅ Extraction dispatcher
extraction_functions = {
    "Wio Bank": extract_wio_transactions,
    "Other Bank (Coming Soon)": extract_other_bank_transactions,
}

# ✅ Upload PDFs
uploaded_files = st.file_uploader("📤 Upload PDF files", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    all_transactions = []

    with st.spinner("🔍 Extracting transactions..."):
        extraction_function = extraction_functions.get(selected_bank)
        for file in uploaded_files:
            transactions = extraction_function(file)
            for transaction in transactions:
                transaction.append(file.name)
            all_transactions.extend(transactions)

    if all_transactions:
        columns = ["Date", "Ref. Number", "Description", "Amount (Incl. VAT)", "Running Balance (Extracted)", "Source File"]
        df = pd.DataFrame(all_transactions, columns=columns)

        # Data cleaning
        df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors='coerce')
        df["Amount (Incl. VAT)"] = df["Amount (Incl. VAT)"].replace({',': ''}, regex=True).astype(float)
        df["Running Balance (Extracted)"] = pd.to_numeric(
            df["Running Balance (Extracted)"].replace({',': ''}, regex=True), errors='coerce'
        )

        # Sort and calculate new balance
        df = df.dropna(subset=["Date"]).sort_values(by="Date").reset_index(drop=True)
        opening_balance = st.number_input("💰 Enter Opening Balance:", value=0.0, step=0.01)
        df["Calculated Balance"] = opening_balance + df["Amount (Incl. VAT)"].cumsum()

        st.success("✅ Transactions extracted successfully!")
        st.dataframe(df, use_container_width=True)
        st.write(f"🔢 **Total Transactions:** {len(df)}")

        # ✅ Download extracted data
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        st.download_button(
            label="📥 Download Consolidated Excel (With Balances)",
            data=output,
            file_name="consolidated_transactions_with_balances.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # ✅ Categorization options
        st.markdown("---")
        st.subheader("📊 Next Step: Categorize Transactions")

        if st.button("🔄 Categorize Now (In This App)"):
            # Placeholder for in-app categorization logic
            st.info("🚀 Categorizing transactions...")
            # Simulate categorization (replace with actual logic or call to another function)
            df["Category"] = df["Description"].apply(lambda x: "Income" if "salary" in x.lower() else "Expense")
            st.success("✅ Transactions categorized!")
            st.dataframe(df, use_container_width=True)
            st.download_button(
                label="📥 Download Categorized Transactions",
                data=output,
                file_name="categorized_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # ✅ External app redirection
        external_categorization_url = "https://your-streamlit-app-link.com"
        if st.button("🌐 Go to Categorization App"):
            st.markdown(f"[👉 Click here to open the Categorization App]({external_categorization_url})", unsafe_allow_html=True)
    else:
        st.warning("⚠️ No transactions found. Please check the PDF format or selected bank.")
