import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px

st.set_page_config(page_title="Gate Operations Control", layout="wide")

# Custom CSS injected directly to handle scroll windows, layout cleanups, and checkbox wrapping
st.markdown("""
    <style>
        .scroll-container {
            max-height: 220px;
            overflow-y: auto;
            border: 1px solid #e6e9ef;
            padding: 12px;
            border-radius: 6px;
            background-color: #fafafa;
        }
        /* Style the checkbox labels to wrap text naturally without truncation */
        div[data-testid="stCheckbox"] label p {
            font-size: 14px !important;
            white-space: normal !important;
            word-break: break-word !important;
            line-height: 1.3 !important;
        }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = "live_tickets.json"

@st.cache_data(ttl=60)
def load_local_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
        
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip()
    
    # HARDENED TIME PARSING: Explicitly handles "Jul 03, 2025 11:29 am" 12-hour AM/PM boundaries
    if "Check-in time" in df.columns:
        df["Check-in time_parsed"] = pd.to_datetime(
            df["Check-in time"].str.strip(), 
            format="%b %d, %Y %I:%M %p", 
            errors="coerce"
        )
        
    return df

df_raw = load_local_data()

if df_raw.empty:
    st.info("Waiting for 'live_tickets.json' to be populated...")
else:
    df_raw["Check-in by"] = df_raw["Check-in by"].fillna("Not Checked In")

    # --- SHARED APP NAVIGATION ---
    st.sidebar.title("Navigation Dashboard")
    page_selection = st.sidebar.radio("Go to view:", ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart"])
    st.sidebar.markdown("---")

    # --- FILTER MANAGEMENT WINDOW (Shared Across Both Pages) ---
    with st.expander("🛠️ Filter Settings (Click to expand / collapse)", expanded=True):
        f_col1, f_col2 = st.columns(2)
        
        with f_col1:
            st.markdown("### Ticket Types")
            all_tickets = sorted(df_raw["Ticket name"].dropna().unique().tolist())
            
            t_action = st.radio(
                "Ticket Shortcuts:", ["Select All", "Deselect All"], 
                horizontal=True, key="t_action_radio"
            )
            
            st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
            selected_tickets = []
            default_val = True if t_action == "Select All" else False
            for i, ticket in enumerate(all_tickets):
                if st.checkbox(ticket, value=default_val, key=f"t_box_{t_action}_{i}"):
                    selected_tickets.append(ticket)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with f_col2:
            st.markdown("### Check-in Agents")
            all_agents = sorted(df_raw["Check-in by"].unique().tolist())
            
            a_action = st.radio(
                "Agent Shortcuts:", ["Select All", "Deselect All"], 
                horizontal=True, key="a_action_radio"
            )
            
            st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
            selected_agents = []
            default_val = True if a_action == "Select All" else False
            for j, agent in enumerate(all_agents):
                if st.checkbox(agent, value=default_val, key=f"a_box_{a_action}_{j}"):
                    selected_agents.append(agent)
            st.markdown('</div>', unsafe_allow_html=True)

    # Apply Filters Globally
    filtered_df = df_raw[
        (df_raw["Ticket name"].isin(selected_tickets)) & 
        (df_raw["Check-in by"].isin(selected_agents))
    ].copy()

    # --- GLOBAL KPI METRICS BAR ---
    total_rows = len(filtered_df)
    checked_in_count = (filtered_df["Status"] == "Checked In").sum()
    
    st.markdown("### Operational KPIs")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Records Selected", f"{total_rows:,}")
    with m2:
        st.metric("Total Checked In", f"{checked_in_count:,}")
    with m3:
        pct = (checked_in_count / total_rows * 100) if total_rows > 0 else 0
        st.metric("Check-In Progress", f"{pct:.1f}%")

    st.markdown("---")

    # =========================================================================
    # PAGE 1: LIVE TRANSACTION LEDGER
    # =========================================================================
    if page_selection == "📋 Live Transaction Ledger":
        st.subheader("Live Operational Records View")
        
        col1, col2 = st.columns(2)
        with col1:
            sort_choice = st.selectbox(
                "Primary Sort Column",
                options=["Check-in time", "Check-in by", "Ticket name", "ID"]
            )
        with col2:
            sort_order = st.radio("Direction", options=["Ascending ⬆️", "Descending ⬇️"], horizontal=True)
        
        is_ascending = sort_order == "Ascending ⬆️"
        
        if sort_choice == "Check-in time":
            filtered_df = filtered_df.sort_values(by="Check-in time_parsed", ascending=is_ascending, na_position="last")
        else:
            filtered_df = filtered_df.sort_values(by=sort_choice, ascending=is_ascending)

        display_cols = [
            "ID", "Order ID", "Confirmation code", "Status",
            "Attendee first name", "Attendee last name", "Ticket name", 
            "Check-in time", "Check-in by"
        ]
        available_display_cols = [c for c in display_cols if c in filtered_df.columns]
        
        st.dataframe(
            filtered_df[available_display_cols],
            use_container_width=True,
            hide_index=True
        )

    # =========================================================================
    # PAGE 2: CHECK-IN ANALYTICS CHART
    # =========================================================================
    elif page_selection == "📊 Check-In Analytics Chart":
        st.subheader("Check-In Velocity Timeline")
        
        # Filter down strictly to rows that contain valid check-in timestamps
        chart_data = filtered_df[filtered_df["Check-in time_parsed"].notna()].copy()
        
        if chart_data.empty:
            st.warning("No checked-in data records match your active global filter criteria layout.")
        else:
            # --- INTERACTIVE VISUAL CONTROL BOX ---
            c1, c2 = st.columns(2)
            with c1:
                time_bucket = st.selectbox(
                    "Timeline Interval Resolution:",
                    options=["15 Minutes", "30 Minutes", "1 Hour", "Raw Cumulative Total"],
                    index=1
                )
            with c2:
                grouping_mode = st.radio(
                    "Color Classification Mode:",
                    options=["Individual Names (Detailed)", "Broad Category Groups (Clean Summary)"],
                    horizontal=True
                )

            def categorized_label(name):
                name_lower = str(name).lower()
                if "all access" in name_lower or "all-access" in name_lower or "staff" in name_lower or "volunteer" in name_lower:
                    return "Staff & All-Access Credentials"
                elif "camping" in name_lower or "lot" in name_lower or "sticker" in name_lower:
                    return "Camping, Lots & Vehicles"
                elif "weekend" in name_lower:
                    return "Standard Weekend Passes"
                elif "single" in name_lower or "only" in name_lower or "friday" in name_lower or "saturday" in name_lower or "sunday" in name_lower:
                    return "Single-Day Base Tickets"
                return "Other / Upcharges / Meals"

            if grouping_mode == "Broad Category Groups (Clean Summary)":
                chart_data["Chart Segment Group"] = chart_data["Ticket name"].apply(categorized_label)
                color_target = "Chart Segment Group"
            else:
                color_target = "Ticket name"

            if time_bucket != "Raw Cumulative Total":
                freq_map = {"15 Minutes": "15min", "30 Minutes": "30min", "1 Hour": "h"}
                chart_data = chart_data.set_index("Check-in time_parsed")
                
                binned_df = chart_data.groupby([pd.Grouper(freq=freq_map[time_bucket]), color_target]).size().reset_index(name="Arrivals Count")
                
                fig = px.bar(
                    binned_df,
                    x="Check-in time_parsed",
                    y="Arrivals Count",
                    color=color_target,
                    title=f"Attendee Peak Entry Traffic Flow (Binned by {time_bucket})",
                    labels={"Check-in time_parsed": "Gate Check-In Time", "Arrivals Count": "Scans Completed"},
                    barmode="stack",
                    height=600,
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                
                fig.update_traces(
                    hovertemplate="<b>%{fullData.name}</b><br>Scans: %{y}<extra></extra>"
                )
            else:
                chart_data = chart_data.sort_values("Check-in time_parsed")
                chart_data["Total Scans Over Time"] = range(1, len(chart_data) + 1)
                
                fig = px.line(
                    chart_data,
                    x="Check-in time_parsed",
                    y="Total Scans Over Time",
                    color=color_target,
                    title="Total Accumulated Gate Entry Speed (Cumulative Curve)",
                    labels={"Check-in time_parsed": "Gate Check-In Time", "Total Scans Over Time": "Total Entry Count Across Gate"},
                    height=600,
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                
                fig.update_traces(
                    hovertemplate="<b>%{fullData.name}</b><br>Total Scans: %{y}<extra></extra>"
                )

            fig.update_layout(
                hovermode="x unified",
                xaxis=dict(title="Gate Check-In Timeline", gridcolor="#f0f0f0"),
                yaxis=dict(title="Scans Completed", gridcolor="#f0f0f0"),
                plot_bgcolor="white",
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1.0,
                    xanchor="left",
                    x=1.02,
                    title_text="Ticket Category Legend"
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)