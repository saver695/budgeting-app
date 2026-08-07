import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Page Setup
st.set_page_config(page_title="Annual Budget Tracker", layout="wide", page_icon="💵")
st.title("Annual Budget Tracker")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Connect to Supabase
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def load_table(table_name, item_col):
    """Fetch rows from Supabase."""
    try:
        response = supabase.table(table_name).select("*").order("id").execute()
        df = pd.DataFrame(response.data)
    except Exception as e:
        df = pd.DataFrame()
    
    if df.empty:
        df = pd.DataFrame(columns=[item_col] + MONTHS)
        df.loc[0] = [""] + [0.0] * 12
    else:
        df = df.drop(columns=["id"], errors="ignore")
    return df

def save_table(df, table_name, item_col):
    """Saves updated budget rows to Supabase cleanly."""
    try:
        # First, clean existing data for this table
        supabase.table(table_name).delete().neq("id", -1).execute()
        
        # Prepare records for insertion
        records = df.to_dict(orient="records")
        clean_records = []
        
        for r in records:
            # Only save rows that have a name filled in
            if r.get(item_col) and str(r.get(item_col)).strip() != "":
                row_data = {item_col: str(r[item_col]).strip()}
                for m in MONTHS:
                    val = r.get(m, 0.0)
                    row_data[m] = float(val) if pd.notnull(val) and val != "" else 0.0
                clean_records.append(row_data)
                
        if clean_records:
            supabase.table(table_name).insert(clean_records).execute()
    except Exception as e:
        st.error(f"Error saving {table_name}: {e}")

# --- STEP 1: LOAD ALL DATA AT STARTUP IF SESSION IS FRESH ---
SECTIONS = [
    ("income", "Income Source"),
    ("spending", "Expense Item"),
    ("savings", "Savings Goal"),
    ("travel", "Travel Destination")
]

for table_name, item_col_name in SECTIONS:
    if f"data_{table_name}" not in st.session_state:
        # Load directly from Supabase into session state before rendering any widget
        st.session_state[f"data_{table_name}"] = load_table(table_name, item_col_name)

# --- STEP 2: RENDER BUDGET SECTIONS ---
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
    
    # Render data editor using pre-loaded session state
    edited_df = st.data_editor(
        st.session_state[f"data_{table_name}"],
        num_rows="dynamic",
        column_config=col_config,
        use_container_width=True,
        key=f"editor_{table_name}"
    )
    
    # Save back to Supabase ONLY if the user actually modified the data
    if not edited_df.equals(st.session_state[f"data_{table_name}"]):
        st.session_state[f"data_{table_name}"] = edited_df
        save_table(edited_df, table_name, item_col_name)
    
    return pd.to_numeric(edited_df[MONTHS].sum(), errors='coerce').fillna(0)

# Render sections & fetch totals
income_totals = render_budget_section("💰 Income", "income", "Income Source")
st.divider()
spending_totals = render_budget_section("💸 Spending", "spending", "Expense Item")
st.divider()
savings_totals = render_budget_section("🏦 Savings", "savings", "Savings Goal")
st.divider()
travel_totals = render_budget_section("✈️ Travel", "travel", "Travel Destination")

# --- STEP 3: SUMMARY SECTION ---
st.header("📊 Annual Summary")

summary_df = pd.DataFrame({
    "Income": income_totals,
    "Spending": spending_totals,
    "Savings": savings_totals,
    "Travel": travel_totals
})

summary_df["Net Remaining"] = (
    summary_df["Income"] 
    - summary_df["Spending"] 
    - summary_df["Savings"] 
    - summary_df["Travel"]
)

st.dataframe(
    summary_df.T, 
    use_container_width=True,
    column_config={month: st.column_config.NumberColumn(format="$%.2f") for month in MONTHS}
)
