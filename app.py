import streamlit as st
import pandas as pd
import json
import os
import datetime
import plotly.express as px

st.set_page_config(page_title="Gate Operations Control", layout="wide")

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
        div[data-testid="stCheckbox"] label p {
            font-size: 14px !important;
            white-space: normal !important;
            word-break: break-word !important;
            line-height: 1.3 !important;
        }
    </style>
""", unsafe_allow_html=True)

LIVE_DATA_FILE = "live_tickets.json"
EXCEL_INVENTORY_FILE = "Gate 2026.xlsx"

# =========================================================================
# ⚙️ STATIC CALENDAR DATE OVERRIDES
# Assign any day name found in your spreadsheet matrix to its absolute calendar date.
# =========================================================================
DAY_TO_DATE_MAPPING = {
    "thursday": "2025-07-03",
    "friday": "2025-07-04",
    "saturday": "2025-07-05",  # Pinned for initial testing
    "sunday": "2025-07-06"
}

@st.cache_data(ttl=60)
def load_local_data():
    if not os.path.exists(LIVE_DATA_FILE):
        return pd.DataFrame(columns=["Check-in time_parsed", "Check-in Day Name", "Check-in by", "Ticket name", "Status"])
        
    with open(LIVE_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip()
    
    # Safely parse and guarantee column structure upfront
    if "Check-in time" in df.columns:
        df["Check-in time_parsed"] = pd.to_datetime(
            df["Check-in time"].str.strip(), 
            format="%b %d, %Y %I:%M %p", 
            errors="coerce"
        )
        df["Check-in Day Name"] = df["Check-in time_parsed"].dt.day_name().str.strip().str.lower()
    else:
        df["Check-in time_parsed"] = pd.NaT
        df["Check-in Day Name"] = ""
        
    if "Check-in by" not in df.columns:
        df["Check-in by"] = "Not Checked In"
    if "Ticket name" not in df.columns:
        df["Ticket name"] = ""
    if "Status" not in df.columns:
        df["Status"] = ""
        
    return df

@st.cache_data(ttl=60)
def load_excel_inventory():
    if not os.path.exists(EXCEL_INVENTORY_FILE):
        return pd.DataFrame()
    try:
        df_inv = pd.read_excel(EXCEL_INVENTORY_FILE)
        df_inv.columns = df_inv.columns.str.strip()
        return df_inv
    except Exception as e:
        st.error(f"Error reading inventory layout from {EXCEL_INVENTORY_FILE}: {e}")
        return pd.DataFrame()

# Helper function for categorizing tickets globally
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

df_raw = load_local_data()
df_excel_registry = load_excel_inventory()

if df_raw.empty:
    st.info("Waiting for 'live_tickets.json' to be populated with transaction entries...")
else:
    df_raw["Check-in by"] = df_raw["Check-in by"].fillna("Not Checked In")
    # Pre-calculate category groups directly onto the master dataset
    df_raw["Broad Category Group"] = df_raw["Ticket name"].apply(categorized_label)

    # --- SIDEBAR NAVIGATION ---
    st.sidebar.title("Navigation Dashboard")
    page_selection = st.sidebar.radio(
        "Go to view:", 
        ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart", "🎒 Per-Bag Inventory Audit"]
    )
    st.sidebar.markdown("---")

    # =========================================================================
    # UNIFIED GLOBAL FILTER PANEL 
    # =========================================================================
    with st.expander("🛠️ Global Dashboard Filter Settings", expanded=True):
        f_col1, f_col2, f_col3 = st.columns([2, 1.5, 2])
        
        with f_col1:
            st.markdown("#### Ticket Clustering & Selection")
            
            # Choose filter methodology upfront
            filter_mode = st.radio(
                "Filter Hierarchy Mode:",
                ["Broad Category Groups (Clean Summary)", "Individual Names (Detailed)"],
                horizontal=True,
                key="global_filter_mode"
            )
            
            t_action = st.radio("Ticket Shortcuts:", ["Select All", "Deselect All"], horizontal=True, key="t_shortcut")
            
            st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
            selected_items = []
            
            if filter_mode == "Broad Category Groups (Clean Summary)":
                unique_categories = sorted(df_raw["Broad Category Group"].unique().tolist())
                for i, cat in enumerate(unique_categories):
                    if st.checkbox(cat, value=(t_action == "Select All"), key=f"cat_g_{i}"):
                        selected_items.append(cat)
            else:
                all_tickets = sorted(df_raw["Ticket name"].dropna().unique().tolist())
                for i, ticket in enumerate(all_tickets):
                    if st.checkbox(ticket, value=(t_action == "Select All"), key=f"t_g_{i}"):
                        selected_items.append(ticket)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with f_col2:
            st.markdown("#### Check-in Agents / Staff")
            all_agents = sorted(df_raw["Check-in by"].unique().tolist())
            a_action = st.radio("Agent Shortcuts:", ["Select All", "Deselect All"], horizontal=True, key="a_shortcut")
            
            st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
            selected_agents = []
            for j, agent in enumerate(all_agents):
                if st.checkbox(agent, value=(a_action == "Select All"), key=f"a_g_{j}"):
                    selected_agents.append(agent)
            st.markdown('</div>', unsafe_allow_html=True)

        with f_col3:
            st.markdown("#### Global Datetime Bounds (Minute Resolution)")
            
            valid_times = df_raw["Check-in time_parsed"].dropna()
            if not valid_times.empty:
                min_time = valid_times.min().replace(second=0, microsecond=0).to_pydatetime()
                max_time = valid_times.max().replace(second=0, microsecond=0).to_pydatetime()
            else:
                min_time = pd.to_datetime("2026-01-01 00:00:00").to_pydatetime()
                max_time = pd.to_datetime("2026-12-31 23:59:00").to_pydatetime()

            if min_time == max_time:
                max_time += datetime.timedelta(minutes=1)

            start_filter, end_filter = st.slider(
                "Filter logs & bag allocations by operational window:",
                min_value=min_time,
                max_value=max_time,
                value=(min_time, max_time),
                step=datetime.timedelta(minutes=1),
                format="MM/DD HH:mm"
            )

    # Apply Target Matrix Filtering Rules safely based on selected mode
    if filter_mode == "Broad Category Groups (Clean Summary)":
        ticket_mask = df_raw["Broad Category Group"].isin(selected_items)
    else:
        ticket_mask = df_raw["Ticket name"].isin(selected_items)

    filtered_df = df_raw[
        ticket_mask & 
        (df_raw["Check-in by"].isin(selected_agents)) & 
        (df_raw["Check-in time_parsed"] >= start_filter) & 
        (df_raw["Check-in time_parsed"] <= end_filter)
    ].copy()

    # --- GLOBAL KPI METRICS BAR ---
    total_rows = len(filtered_df)
    checked_in_count = (filtered_df["Status"] == "Checked In").sum()
    
    st.markdown("### Operational KPIs")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Records Filtered", f"{total_rows:,}")
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
            sort_choice = st.selectbox("Primary Sort Column", options=["Check-in time", "Check-in by", "Ticket name", "Broad Category Group", "ID"])
        with col2:
            sort_order = st.radio("Direction", options=["Ascending ⬆️", "Descending ⬇️"], horizontal=True)
        
        is_ascending = sort_order == "Ascending ⬆️"
        if sort_choice == "Check-in time":
            filtered_df = filtered_df.sort_values(by="Check-in time_parsed", ascending=is_ascending, na_position="last")
        else:
            filtered_df = filtered_df.sort_values(by=sort_choice, ascending=is_ascending)
            
        display_cols = ["ID", "Order ID", "Confirmation code", "Status", "Attendee first name", "Attendee last name", "Ticket name", "Broad Category Group", "Check-in time", "Check-in by"]
        available_display_cols = [c for c in display_cols if c in filtered_df.columns]
        st.dataframe(filtered_df[available_display_cols], use_container_width=True, hide_index=True)

    # =========================================================================
    # PAGE 2: CHECK-IN ANALYTICS CHART
    # =========================================================================
    elif page_selection == "📊 Check-In Analytics Chart":
        st.subheader("Check-In Velocity Timeline")
        chart_data = filtered_df[filtered_df["Check-in time_parsed"].notna()].copy()
        if chart_data.empty:
            st.warning("No data matches the selected timeframe bounds or global filter criteria.")
        else:
            c1 = st.columns(1)[0]
            with c1:
                time_bucket = st.selectbox("Timeline Interval Resolution:", options=["15 Minutes", "30 Minutes", "1 Hour", "Raw Cumulative Total"], index=1)
            
            # Inherit visual target color classification directly from the Global filter selection mode
            if filter_mode == "Broad Category Groups (Clean Summary)":
                color_target = "Broad Category Group"
            else:
                color_target = "Ticket name"

            if time_bucket != "Raw Cumulative Total":
                freq_map = {"15 Minutes": "15min", "30 Minutes": "30min", "1 Hour": "h"}
                chart_data = chart_data.set_index("Check-in time_parsed")
                binned_df = chart_data.groupby([pd.Grouper(freq=freq_map[time_bucket]), color_target]).size().reset_index(name="Arrivals Count")
                fig = px.bar(binned_df, x="Check-in time_parsed", y="Arrivals Count", color=color_target, barmode="stack", height=600, color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                chart_data = chart_data.sort_values("Check-in time_parsed")
                chart_data["Total Scans Over Time"] = range(1, len(chart_data) + 1)
                fig = px.line(chart_data, x="Check-in time_parsed", y="Total Scans Over Time", color=color_target, height=600, color_discrete_sequence=px.colors.qualitative.Bold)

            fig.update_layout(hovermode="x unified", plot_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

    # =========================================================================
    # PAGE 3: PER-BAG INVENTORY AUDIT
    # =========================================================================
    elif page_selection == "🎒 Per-Bag Inventory Audit":
        st.subheader("Global Filter-Bound Performance Reconciliation Ledger")
        
        if df_excel_registry.empty:
            st.warning(f"Could not load tracking information from '{EXCEL_INVENTORY_FILE}'.")
        else:
            bag_label = "Bag Number" if "Bag Number" in df_excel_registry.columns else df_excel_registry.columns[0]
            gate_label = "Gate" if "Gate" in df_excel_registry.columns else "Gate"
            day_label = "Day" if "Day" in df_excel_registry.columns else "Day"
            name_label = "Name" if "Name" in df_excel_registry.columns else "Name"
            start_time_label = "Shift Start" if "Shift Start" in df_excel_registry.columns else "Shift Start"
            end_time_label = "Shift End" if "Shift End" in df_excel_registry.columns else "Shift End"

            metadata_columns = [bag_label, gate_label, name_label, start_time_label, end_time_label, day_label, "Shift"]
            ticket_item_columns = [col for col in df_excel_registry.columns if col not in metadata_columns]

            checked_in_only = filtered_df[filtered_df["Status"] == "Checked In"].copy()
            if not checked_in_only.empty:
                checked_in_only["Agent_Lower"] = checked_in_only["Check-in by"].str.lower().str.strip()
                checked_in_only["Ticket_Lower"] = checked_in_only["Ticket name"].str.lower().str.strip()
            else:
                checked_in_only["Agent_Lower"] = pd.Series(dtype=str)
                checked_in_only["Ticket_Lower"] = pd.Series(dtype=str)

            cat_lower_map = {cat: cat.lower().strip() for cat in ticket_item_columns}
            consolidated_bags = []

            for _, row in df_excel_registry.iterrows():
                day_assigned_str = str(row.get(day_label, "")).strip().lower()
                shift_start_str = str(row.get(start_time_label, "")).strip()
                shift_end_str = str(row.get(end_time_label, "")).strip()
                
                if day_assigned_str in DAY_TO_DATE_MAPPING:
                    target_calendar_date = pd.to_datetime(DAY_TO_DATE_MAPPING[day_assigned_str]).date()
                else:
                    sample_day_matches = df_raw[df_raw["Check-in Day Name"] == day_assigned_str]
                    if not sample_day_matches.empty:
                        target_calendar_date = sample_day_matches["Check-in time_parsed"].iloc[0].date()
                    else:
                        valid_p = df_raw["Check-in time_parsed"].dropna()
                        if not valid_p.empty:
                            target_calendar_date = valid_p.min().date()
                        else:
                            target_calendar_date = datetime.date(2025, 7, 5)

                bag_number = str(row.get(bag_label, "N/A"))
                gate_assigned = str(row.get(gate_label, "N/A"))
                day_assigned = str(row.get(day_label, ""))
                staff_name = str(row.get(name_label, "N/A"))

                try:
                    parsed_start_time = pd.to_datetime(shift_start_str, format="%H:%M", errors='coerce').time()
                    if pd.isna(parsed_start_time): parsed_start_time = datetime.time(0, 0)
                except:
                    parsed_start_time = datetime.time(0, 0)
                    print(bag_number)

                try:
                    parsed_end_time = pd.to_datetime(shift_end_str, format="%H:%M", errors='coerce').time()
                    #print(parsed_end_time)
                    if pd.isna(parsed_end_time): parsed_end_time = datetime.time(23, 59)
                except:
                    parsed_end_time = datetime.time(23, 59)
                    #print(bag_number)

                bag_shift_datetime_start = datetime.datetime.combine(target_calendar_date, parsed_start_time)
                bag_shift_datetime_end = datetime.datetime.combine(target_calendar_date, parsed_end_time)

                if bag_shift_datetime_end < bag_shift_datetime_start:
                    bag_shift_datetime_end += datetime.timedelta(days=1)

                if (bag_shift_datetime_end < start_filter) or (bag_shift_datetime_start > end_filter):
                    continue

                is_fully_within = (bag_shift_datetime_start >= start_filter) and (bag_shift_datetime_end <= end_filter)


                
                bag_total_initial_qty = 0
                bag_total_scans = 0
                staff_name_clean = staff_name.lower().strip()
                
                scans_by_this_staff_in_window = checked_in_only[
                    (checked_in_only["Agent_Lower"] == staff_name_clean) &
                    (checked_in_only["Check-in time_parsed"] >= bag_shift_datetime_start) &
                    (checked_in_only["Check-in time_parsed"] <= bag_shift_datetime_end)
                ]

                for category in ticket_item_columns:
                    try: allocation_qty = int(row.get(category, 0))
                    except: allocation_qty = 0

                    if allocation_qty > 0:
                        bag_total_initial_qty += allocation_qty
                        
                        if not scans_by_this_staff_in_window.empty:
                            cat_lower = cat_lower_map[category]
                            matched_count = scans_by_this_staff_in_window["Ticket_Lower"].str.contains(cat_lower, na=False).sum()
                            bag_total_scans += matched_count

                differential = bag_total_initial_qty - bag_total_scans
                
                consolidated_bags.append({
                    "Bag Number": bag_number,
                    "Gate Location": gate_assigned,
                    "Day Code": day_assigned,
                    "Shift Window": f"{shift_start_str} - {shift_end_str}",
                    "Assigned Attendant": staff_name,
                    "Initial Pre-Pack Qty": bag_total_initial_qty,
                    "Total Scanned Counts": bag_total_scans,
                    "Differential Variance (+ / -)": differential,
                    "_is_fully_within": is_fully_within 
                })

            if consolidated_bags:
                df_consolidated_master = pd.DataFrame(consolidated_bags)
            else:
                df_consolidated_master = pd.DataFrame(columns=[
                    "Bag Number", "Gate Location", "Day Code", "Shift Window", 
                    "Assigned Attendant", "Initial Pre-Pack Qty", "Total Scanned Counts", "Differential Variance (+ / -)", "_is_fully_within"
                ])
            
            def highlight_shift_window(row):
                styles = [''] * len(row)
                if not row["_is_fully_within"]:
                    try:
                        idx = row.index.get_loc("Shift Window")
                        styles[idx] = "background-color: #fef08a; color: #854d0e; font-weight: bold;"
                    except:
                        pass
                return styles

            styled_master_df = df_consolidated_master.style.apply(highlight_shift_window, axis=1)

            st.markdown(f"### 📋 Reconciled Bag Audit Ledger ({len(df_consolidated_master)} Active Shifts In Selected Range)")
            st.dataframe(
                styled_master_df,
                use_container_width=True,
                hide_index=True,
                column_config={"_is_fully_within": None}
            )