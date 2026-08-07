import streamlit as st
import pandas as pd

# Page Configuration
st.set_page_config(page_title="Annual Budget Tracker", layout="wide", page_icon="💵")
st.title("Annual Budget Tracker")

# Define the months for our columns
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def init_dataframe(item_name):
    """Initializes an empty dataframe with an item column and 12 month columns."""
    df = pd.DataFrame(columns=[item_name] + MONTHS)
    df.loc[0] = [""] + [0.0] * 12
    return df

# Initialize session state so data persists during interaction
if "income" not in st.session_state:
    st.session_state.income = init_dataframe("Income Source")
    st.session_state.spending = init_dataframe("Expense Item")
    st.session_state.savings = init_dataframe("Savings Goal")
    st.session_state.travel = init_dataframe("Travel Destination")

def render_budget_section(title, state_key, item_col_name):
    """Renders a dynamic data editor for a specific budget category."""
    st.subheader(title)
    
    # Configure columns to enforce dollar formatting and proper types
    col_config = {item_col_name: st.column_config.TextColumn(item_col_name, required=True)}
    for month in MONTHS:
        col_config[month] = st.column_config.NumberColumn(
            month, 
            format="$%.2f", 
            default=0.0, 
            step=10.0
        )
    
    # Render the interactive dataframe
    edited_df = st.data_editor(
        st.session_state[state_key],
        num_rows="dynamic",
        column_config=col_config,
        use_container_width=True,
        key=f"editor_{state_key}"
    )
    
    # Update state and return the monthly sums for this category
    st.session_state[state_key] = edited_df
    # Ensure numeric types before summing to avoid errors with empty cells
    return pd.to_numeric(edited_df[MONTHS].sum(), errors='coerce').fillna(0)

# Render sections and capture their monthly totals
income_totals = render_budget_section("💰 Income", "income", "Income Source")
st.divider()
spending_totals = render_budget_section("💸 Spending", "spending", "Expense Item")
st.divider()
savings_totals = render_budget_section("🏦 Savings", "savings", "Savings Goal")
st.divider()
travel_totals = render_budget_section("✈️ Travel", "travel", "Travel Destination")

# Calculate and display the summary
st.header("📊 Annual Summary")

summary_df = pd.DataFrame({
    "Income": income_totals,
    "Spending": spending_totals,
    "Savings": savings_totals,
    "Travel": travel_totals
})

# Calculate net remaining cash flow per month
summary_df["Net Remaining"] = (
    summary_df["Income"] 
    - summary_df["Spending"] 
    - summary_df["Savings"] 
    - summary_df["Travel"]
)

# Format the summary table for display
st.dataframe(
    summary_df.T, 
    use_container_width=True,
    column_config={month: st.column_config.NumberColumn(format="$%.2f") for month in MONTHS}
)
