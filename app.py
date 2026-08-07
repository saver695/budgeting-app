import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Page Setup
st.set_page_config(page_title="Personal Banking & Expense Dashboard", layout="wide", page_icon="🏦")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# --- DATABASE HELPERS ---
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def load_table(table_name, item_col):
    """Fetch database rows into Pandas."""
    try:
        supabase = get_supabase()
        response = supabase.table(table_name).select("*").order("id").execute()
        df = pd.DataFrame(response.data)
    except Exception:
        df = pd.DataFrame()
    
    if df.empty:
        df = pd.DataFrame(columns=[item_col] + MONTHS)
        df.loc[0] = [""] + [0.0] * 12
    else:
        df = df.drop(columns=["id"], errors="ignore")
    return df

def extract_dataframe_from_editor(table_name, item_col):
    """Reconstructs the active Dataframe using base data + live widget state."""
    base_df = st.session_state[f"data_{table_name}"].copy()
    editor_key = f"editor_{table_name}"
    
    if editor_key in st.session_state:
        editor_state = st.session_state[editor_key]
        
        # Apply edited cells
        for row_idx, updated_cols in editor_state.get("edited_rows", {}).items():
            for col_name, val in updated_cols.items():
                if row_idx < len(base_df):
                    base_df.iat[row_idx, base_df.columns.get_loc(col_name)] = val

        # Remove deleted rows
        deleted_rows = editor_state.get("deleted_rows", [])
        if deleted_rows:
            base_df = base_df.drop(index=deleted_rows).reset_index(drop=True)

        # Append added rows
        added_rows = editor_state.get("added_rows", [])
        if added_rows:
            new_rows_df = pd.DataFrame(added_rows)
            base_df = pd.concat([base_df, new_rows_df], ignore_index=True)

    return base_df

def save_all_data():
    """Extracts edits from mandatory, discretionary, income, and savings editors and persists to Supabase."""
    supabase = get_supabase()
    SECTIONS = [
        ("income", "Income Source"),
        ("mandatory_spending", "Expense Item"),
        ("discretionary_spending", "Expense Item"),
        ("savings", "Savings Goal")
    ]
    
    try:
        for table_name, item_col in SECTIONS:
            base_df = extract_dataframe_from_editor(table_name, item_col)

            clean_records = []
            for r in base_df.to_dict(orient="records"):
                item_val = r.get(item_col)
                if pd.notnull(item_val) and str(item_val).strip() != "":
                    row_data = {item_col: str(item_val).strip()}
                    for m in MONTHS:
                        val = r.get(m, 0.0)
                        row_data[m] = float(val) if pd.notnull(val) and str(val).strip() != "" else 0.0
                    clean_records.append(row_data)

            # Atomic table wipe & overwrite
            supabase.table(table_name).delete().neq("id", -1).execute()
            if clean_records:
                supabase.table(table_name).insert(clean_records).execute()
                
            st.session_state[f"data_{table_name}"] = load_table(table_name, item_col)
            
        st.success("Bank records updated successfully!")
    except Exception as e:
        st.error(f"Error updating records: {e}")

# --- 1. INITIALIZE DATA IN SESSION STATE ---
SECTIONS = [
    ("income", "Income Source"),
    ("mandatory_spending", "Expense Item"),
    ("discretionary_spending", "Expense Item"),
    ("savings", "Savings Goal")
]

for table_name, item_col_name in SECTIONS:
    if f"data_{table_name}" not in st.session_state:
        st.session_state[f"data_{table_name}"] = load_table(table_name, item_col_name)

# --- 2. HEADER & ACTION BAR ---
st.title("Banking & Financial Dashboard")

col_head1, col_head2 = st.columns([4, 1])
with col_head2:
    if st.button("Save Changes", type="primary", use_container_width=True):
        save_all_data()

st.divider()

# --- 3. HELPER FOR RENDERING TABLES ---
def render_budget_section(title, table_name, item_col_name):
    st.subheader(title)
    
    col_config = {item_col_name: st.column_config.TextColumn(item_col_name, required=True)}
    for month in MONTHS:
        col_config[month] = st.column_config.NumberColumn(
            month, 
            format="$%.2f", 
            default=0.0, 
            step=10.0
        )
    
    edited_df = st.data_editor(
        st.session_state[f"data_{table_name}"],
        num_rows="dynamic",
        column_config=col_config,
        use_container_width=True,
        key=f"editor_{table_name}"
    )
    
    return pd.to_numeric(edited_df[MONTHS].sum(), errors='coerce').fillna(0)

# --- 4. TABS NAVIGATION ---
tab_dashboard, tab_income, tab_mandatory, tab_discretionary, tab_savings = st.tabs([
    "Dashboard", 
    "Income", 
    "Mandatory Expenses", 
    "Discretionary Expenses", 
    "Savings & Investments"
])

with tab_income:
    income_totals = render_budget_section("Income Sources", "income", "Income Source")

with tab_mandatory:
    mandatory_totals = render_budget_section("Mandatory / Fixed Spending (Rent, Utilities, Insurance)", "mandatory_spending", "Expense Item")

with tab_discretionary:
    discretionary_totals = render_budget_section("Discretionary / Variable Spending (Dining, Travel, Hobbies)", "discretionary_spending", "Expense Item")

with tab_savings:
    savings_totals = render_budget_section("Savings Goals & Investments", "savings", "Savings Goal")

# --- 5. DASHBOARD SUMMARY & SPENDING TRACKER ---
with tab_dashboard:
    annual_income = income_totals.sum()
    annual_mandatory = mandatory_totals.sum()
    annual_discretionary = discretionary_totals.sum()
    annual_savings = savings_totals.sum()
    total_spending = annual_mandatory + annual_discretionary
    net_position = annual_income - (total_spending + annual_savings)

    # Key Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Annual Income", f"${annual_income:,.2f}")
    m2.metric("Mandatory Expenses", f"${annual_mandatory:,.2f}", delta_color="inverse")
    m3.metric("Discretionary Expenses", f"${annual_discretionary:,.2f}", delta_color="inverse")
    m4.metric("Savings & Investments", f"${annual_savings:,.2f}")
    m5.metric(
        "Net Cash Flow", 
        f"${net_position:,.2f}", 
        delta=f"{(net_position/annual_income*100):.1f}% Margin" if annual_income > 0 else "0%"
    )

    st.divider()

    # Visual Spending Tracker
    col_chart1, col_chart2 = st.columns([3, 2])

    with col_chart1:
        st.subheader("Monthly Cash Flow Breakdown")
        monthly_df = pd.DataFrame({
            "Income": income_totals,
            "Mandatory Spending": mandatory_totals,
            "Discretionary Spending": discretionary_totals,
            "Savings": savings_totals
        })
        st.bar_chart(monthly_df, height=350)

    with col_chart2:
        st.subheader("Expense Split (Mandatory vs Discretionary)")
        if total_spending > 0:
            split_df = pd.DataFrame({
                "Category": ["Mandatory Expenses", "Discretionary Expenses"],
                "Amount": [annual_mandatory, annual_discretionary]
            })
            st.dataframe(
                split_df, 
                use_container_width=True,
                column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")}
            )
            
            mandatory_pct = (annual_mandatory / total_spending) * 100
            discretionary_pct = (annual_discretionary / total_spending) * 100
            
            st.progress(mandatory_pct / 100, text=f"Mandatory: {mandatory_pct:.1f}%")
            st.progress(discretionary_pct / 100, text=f"Discretionary: {discretionary_pct:.1f}%")
        else:
            st.info("Add spending records to view your expense breakdown.")

    st.divider()

    # Comprehensive Ledger Table
    st.subheader("📋 Annual Financial Statement")
    ledger_df = pd.DataFrame({
        "Income": income_totals,
        "Mandatory Expenses": mandatory_totals,
        "Discretionary Expenses": discretionary_totals,
        "Total Expenses": mandatory_totals + discretionary_totals,
        "Savings": savings_totals,
        "Net Remaining": income_totals - (mandatory_totals + discretionary_totals + savings_totals)
    })

    st.dataframe(
        ledger_df.T, 
        use_container_width=True,
        column_config={month: st.column_config.NumberColumn(format="$%.2f") for month in MONTHS}
    )
