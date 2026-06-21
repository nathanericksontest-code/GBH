import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# Set page config to wide mode for a better dashboard layout
st.set_page_config(page_title="Ticket Sales Dashboard", layout="wide")

st.title("🎟️ Ticket Sales Statistics Dashboard")
st.markdown("Interact with the filters below to explore real-time sales data.")

# --- 1. LOAD DATA ---
# Replace this with your actual data loading logic (e.g., pd.read_csv("your_data.csv"))
@st.cache_data
def load_data():
    np.random.seed(42)
    dates = pd.date_range(start="2026-06-01", end="2026-06-20", freq="D")
    
    data = []
    for date in dates:
        # Simulate General Admission and VIP sales
        data.append({"Date": date, "Ticket Type": "General Admission", "Quantity": np.random.randint(10, 50), "Price": 50})
        data.append({"Date": date, "Ticket Type": "VIP", "Quantity": np.random.randint(2, 12), "Price": 150})
        
    df = pd.DataFrame(data)
    df["Revenue"] = df["Quantity"] * df["Price"]
    return df

df = load_data()

# --- 2. SIDEBAR FILTERS (Interactivity) ---
st.sidebar.header("Filter Options")

# Ticket Type Filter
ticket_types = df["Ticket Type"].unique()
selected_types = st.sidebar.multiselect("Select Ticket Type:", options=ticket_types, default=ticket_types)

# Date Filter
min_date = df["Date"].min().to_pydatetime()
max_date = df["Date"].max().to_pydatetime()
selected_dates = st.sidebar.slider("Select Date Range:", min_value=min_date, max_value=max_date, value=(min_date, max_date))

# Filter the dataframe based on user input
filtered_df = df[
    (df["Ticket Type"].isin(selected_types)) & 
    (df["Date"] >= selected_dates[0]) & 
    (df["Date"] <= selected_dates[1])
]

# --- 3. KEY METRICS ---
total_revenue = filtered_df["Revenue"].sum()
total_tickets = filtered_df["Quantity"].sum()
avg_ticket_price = total_revenue / total_tickets if total_tickets > 0 else 0

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Total Revenue", value=f"${total_revenue:,.2f}")
with col2:
    st.metric(label="Tickets Sold", value=f"{total_tickets:,}")
with col3:
    st.metric(label="Average Ticket Price", value=f"${avg_ticket_price:,.2f}")

st.markdown("---")

# --- 4. INTERACTIVE CHARTS ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Sales Trends Over Time")
    # Group data by date for the line chart
    time_df = filtered_df.groupby("Date")["Quantity"].sum().reset_index()
    fig_line = px.line(time_df, x="Date", y="Quantity", labels={"Quantity": "Tickets Sold"}, markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

with chart_col2:
    st.subheader("Revenue by Ticket Type")
    # Group data by ticket type for the pie chart
    type_df = filtered_df.groupby("Ticket Type")["Revenue"].sum().reset_index()
    fig_pie = px.pie(type_df, values="Revenue", names="Ticket Type", hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

# --- 5. DATA TABLE ---
st.subheader("Raw Data View")
st.dataframe(filtered_df, use_container_width=True)