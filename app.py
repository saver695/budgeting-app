import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Page Setup
st.set_page_config(page_title="Annual Budget Tracker", layout="wide", page_icon="💵")
st.title("Annual Budget Tracker")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

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

def save_all_data():
    """Extracts edits directly from Streamlit's data editor state and saves to Supabase."""
    supabase = get_supabase()
    SECTIONS = [
        ("income", "Income Source"),
        ("spending", "Expense Item"),
        ("savings", "Savings Goal"),
        ("travel", "Travel Destination")
    ]
    
    try:
        for table_name, item_col in SECTIONS:
            # Base table stored in session state
            base_df = st.session_state[f"data_{table_name}"].copy()
            editor_key = f"editor_{table_name}"
            
            # Reconstruct the edited dataframe if edits exist
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

            clean_records = []
            for r in base_df.to_dict(orient="records"):
                item_val = r.get(item_col)
                if pd.notnull(item_val) and str(item_val).strip() != "":
                    row_data = {item_col: str(item_val).strip()}
                    for m in MONTHS:
                        val = r.get(m, 0.0)
                        row_data[m] = float(val) if pd.notnull(val) and str(val).strip() != "" else 0.0
                    clean_records.append(row_data)

            # Replace old records in Supabase
            supabase.table(table_name).delete().neq("id", -1).execute()
            if clean_records:
                supabase.table(table_name).insert(clean_records).execute()
                
            # Refresh local session state
            st.session_state[f"data_{table_name}"] = load_table(table_name, item_col)
            
        st.success("All budget changes saved successfully to Supabase!")
    except Exception as e:
        st.error(f"Error saving budget: {e}")

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

# --- 2. TOP ACTION BAR ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Save All Changes", type="primary", use_container_width=True):
        save_all_data()

st.divider()

# --- 3. RENDER BUDGET SECTIONS ---
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

income_totals = render_budget_section("💰 Income", "income", "Income Source")
st.divider()
spending_totals = render_budget_section("💸 Spending", "spending", "Expense Item")
st.divider()
savings_totals = render_budget_section("🏦 Savings", "savings", "Savings Goal")
st.divider()
travel_totals = render_budget_section("✈️ Travel", "travel", "Travel Destination")

# --- 4. ANNUAL SUMMARY ---
st.header("Annual Summary")

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
