import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Page Setup
st.set_page_config(page_title="Annual Budget Tracker", layout="wide", page_icon="💵")
st.title("Annual Budget Tracker")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Connect to Supabase directly without caching bugs
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def load_table(table_name, item_col):
    """Fetch database rows into Pandas."""
    try:
        supabase = get_supabase()
        response = supabase.table(table_name).select("*").order("id").execute()
        df = pd.DataFrame(response.data)
    except Exception as e:
        df = pd.DataFrame()
    
    if df.empty:
        df = pd.DataFrame(columns=["id", item_col] + MONTHS)
        df.loc[0] = [None, ""] + [0.0] * 12
    elif "id" not in df.columns:
        df["id"] = None
        
    return df

def sync_changes(table_name, item_col):
    """Callback function that runs ONLY when a table is explicitly edited."""
    editor_key = f"editor_{table_name}"
    changes = st.session_state.get(editor_key, {})
    supabase = get_supabase()
    
    # 1. Handle Added Rows
    for row in changes.get("added_rows", []):
        item_val = row.get(item_col)
        if item_val and str(item_val).strip() != "":
            new_row = {item_col: str(item_val).strip()}
            for m in MONTHS:
                val = row.get(m, 0.0)
                new_row[m] = float(val) if val else 0.0
            supabase.table(table_name).insert(new_row).execute()

    # 2. Handle Edited Cells
    edited_rows = changes.get("edited_rows", {})
    if edited_rows:
        current_df = st.session_state[f"data_{table_name}"]
        for row_idx, updated_cols in edited_rows.items():
            db_id = current_df.iloc[row_idx].get("id")
            if pd.notnull(db_id):
                update_payload = {}
                for col, val in updated_cols.items():
                    if col == item_col:
                        update_payload[col] = str(val).strip()
                    elif col in MONTHS:
                        update_payload[col] = float(val) if val else 0.0
                if update_payload:
                    supabase.table(table_name).update(update_payload).eq("id", int(db_id)).execute()

    # 3. Handle Deleted Rows
    for row_idx in changes.get("deleted_rows", []):
        current_df = st.session_state[f"data_{table_name}"]
        db_id = current_df.iloc[row_idx].get("id")
        if pd.notnull(db_id):
            supabase.table(table_name).delete().eq("id", int(db_id)).execute()

    # Reload database data into state
    st.session_state[f"data_{table_name}"] = load_table(table_name, item_col)

# --- 1. INITIALIZE DATA IN SESSION STATE ---
SECTIONS = [
    ("income", "Income Source"),
    ("spending", "Expense Item"),
    ("savings", "Savings Goal"),
    ("travel", "Travel Destination")
]

for table_name, item_col_name in SECTIONS:
    if f"data_{table_name}" not in st.session_state:
        st.session_state[f"data_{table_name}"] = load_table(table_name, item_col_name)

# --- 2. RENDER SECTIONS ---
def render_budget_section(title, table_name, item_col_name):
    st.subheader(title)
    
    col_config = {
        "id": None,  # Hide internal ID column from view
        item_col_name: st.column_config.TextColumn(item_col_name, required=True)
    }
    for month in MONTHS:
        col_config[month] = st.column_config.NumberColumn(
            month, 
            format="$%.2f", 
            default=0.0, 
            step=10.0
        )
    
    # Event-driven table syncing via on_change
    st.data_editor(
        st.session_state[f"data_{table_name}"],
        num_rows="dynamic",
        column_config=col_config,
        use_container_width=True,
        key=f"editor_{table_name}",
        on_change=sync_changes,
        args=(table_name, item_col_name)
    )
    
    df = st.session_state[f"data_{table_name}"]
    return pd.to_numeric(df[MONTHS].sum(), errors='coerce').fillna(0)

# Render tables
income_totals = render_budget_section("💰 Income", "income", "Income Source")
st.divider()
spending_totals = render_budget_section("💸 Spending", "spending", "Expense Item")
st.divider()
savings_totals = render_budget_section("🏦 Savings", "savings", "Savings Goal")
st.divider()
travel_totals = render_budget_section("✈️ Travel", "travel", "Travel Destination")

# --- 3. ANNUAL SUMMARY ---
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
