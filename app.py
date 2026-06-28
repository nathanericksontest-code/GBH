import streamlit as st
import pandas as pd
import json
import os
import datetime
import plotly.express as px
from google.oauth2 import service_account
import gspread
from dotenv import load_dotenv

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


# =========================================================================
# 🔐 GOOGLE SHEETS & ACCESS SECURITY SETTINGS
# =========================================================================

load_dotenv()

GOOGLE_SHEET_COUNTER_URL = os.environ.get("GOOGLE_SHEET_COUNTER_URL")
GOOGLE_SHEET_PREPACK_URL = os.environ.get("GOOGLE_SHEET_PREPACK_URL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

DAY_TO_DATE_MAPPING = {
    "thursday": "2025-07-03",
    "friday": "2025-07-04",
    "saturday": "2025-07-05",  
    "sunday": "2025-07-06"
}


@st.cache_data(ttl=10)
def load_local_data():
    if not os.path.exists(LIVE_DATA_FILE):
        return pd.DataFrame(columns=["Check-in time_parsed", "Check-in Day Name", "Check-in by", "Ticket name", "Status"])
    with open(LIVE_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip()
    
    if "Check-in time" in df.columns:
        df["Check-in time_parsed"] = pd.to_datetime(df["Check-in time"].str.strip(), format="%b %d, %Y %I:%M %p", errors="coerce")
        df["Check-in Day Name"] = df["Check-in time_parsed"].dt.day_name().str.strip().str.lower()
    else:
        df["Check-in time_parsed"] = pd.NaT
        df["Check-in Day Name"] = ""
    return df

@st.cache_data(ttl=10)
def load_google_sheet_inventory(url):
    try:
        df_inv = pd.read_csv(url)
        df_inv.columns = df_inv.columns.str.strip()
        if df_inv.empty or "function" in str(df_inv.iloc[0,0]) or "/*" in str(df_inv.iloc[0,0]):
            st.error("🛑 App fetched HTML wrapper instead of data. Check sharing permissions or CSV URL formatting!")
            return pd.DataFrame()
        return df_inv
    except Exception as e:
        st.error(f"Error fetching inventory layout: {e}")
        return pd.DataFrame()

def categorized_label(name):
    name_lower = str(name).lower()
    if "all access" in name_lower or "all-access" in name_lower or "staff" in name_lower or "volunteer" in name_lower:
        return "Staff & All-Access Credentials"
    elif "camping" in name_lower or "lot" in name_lower or "sticker" in name_lower:
        return "Camping, Lots & Vehicles"
    elif "weekend" in name_lower:
        return "Standard Weekend Passes"
    return "Other / Upcharges / Meals"

df_raw = load_local_data()

# --- SIDEBAR NAVIGATION (NOW FEATURING 4 PAGES) ---
st.sidebar.title("Navigation Dashboard")
page_selection = st.sidebar.radio(
    "Go to view:", 
    ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart", "🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations", "📝 TEST"]
)
st.sidebar.markdown("---")

# =========================================================================
# 🔒 PASSWORD PROTECTION GATE (Applies to all pages)
# =========================================================================
is_authenticated = False
#if page_selection in ["🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations"]:
st.sidebar.subheader("🔒 Authentication Required")
user_password = st.sidebar.text_input("Enter Inventory Access Password:", type="password")
if True:# FIXXX user_password == APP_PASSWORD:
    st.sidebar.success("Access Granted!")
    is_authenticated = True
else:
    if user_password != "": st.sidebar.error("Incorrect Password")
    is_authenticated = False

# Fetch fresh copy from the cloud if authenticated
any_page = ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart", "🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations", "📝 TEST"]
if is_authenticated and page_selection in ["🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations","📝 TEST"]:
    df_excel_registry = load_google_sheet_inventory(GOOGLE_SHEET_PREPACK_URL)
    df_excel_counted = load_google_sheet_inventory(GOOGLE_SHEET_COUNTER_URL)
else:
    df_excel_registry = pd.DataFrame()

# =========================================================================
# MAIN DASHBOARD LOGIC
# =========================================================================
if not is_authenticated:
    st.warning("🔒 Access Denied. Please authenticate via the sidebar panel.")
elif df_raw.empty:
    st.info("Waiting for 'live_tickets.json' to populate...")
else:
    df_raw["Check-in by"] = df_raw["Check-in by"].fillna("Not Checked In")
    
    df_raw["Broad Category Group"] = df_raw["Ticket name"].apply(categorized_label)

    # Global variables required across analytical screens
    start_filter, end_filter = datetime.datetime.now(), datetime.datetime.now()
    filter_mode = "Broad Category Groups (Clean Summary)"
    selected_items, selected_agents = [], []

    # Render filters only on diagnostic analytics pages
    if page_selection in any_page:
        with st.expander("🛠️ Global Dashboard Filter Settings", expanded=True):
            f_col1, f_col2, f_col3 = st.columns([2, 1.5, 2])
            with f_col1:
                st.markdown("#### Ticket Clustering & Selection")
                filter_mode = st.radio("Filter Hierarchy Mode:", ["Broad Category Groups (Clean Summary)", "Individual Names (Detailed)"], horizontal=True)
                t_action = st.radio("Ticket Shortcuts:", ["Select All", "Deselect All"], horizontal=True)
                st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
                if filter_mode == "Broad Category Groups (Clean Summary)":
                    unique_categories = sorted(df_raw["Broad Category Group"].unique().tolist())
                    for i, cat in enumerate(unique_categories):
                        # ⭐ THE TWEAK: Make the key unique using t_action and filter_mode
                        unique_key = f"c_{i}_{filter_mode.lower()[0:4]}_{t_action.lower().replace(' ', '_')}"
                        
                        if st.checkbox(cat, value=(t_action == "Select All"), key=unique_key): 
                            selected_items.append(cat)
                else:
                    all_tickets = sorted(df_raw["Ticket name"].dropna().unique().tolist())
                    for i, ticket in enumerate(all_tickets):
                        # ⭐ THE TWEAK: Make the key unique using t_action and filter_mode
                        unique_key = f"t_{i}_{filter_mode.lower()[0:4]}_{t_action.lower().replace(' ', '_')}"
                        
                        if st.checkbox(ticket, value=(t_action == "Select All"), key=unique_key): 
                            selected_items.append(ticket)
                            
                st.markdown('</div>', unsafe_allow_html=True)
            with f_col2:
                st.markdown("#### Check-in Agents / Staff")
                all_agents = sorted(df_raw["Check-in by"].unique().tolist())
                print(all_agents)
                a_action = st.radio("Agent Shortcuts:", ["Select All", "Deselect All"], horizontal=True)
                st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
                selected_agents = [] # Make sure this list is initialized right before the loop
                for j, agent in enumerate(all_agents):
                    # ⭐ THE TWEAK: Adding a_action to the key forces a total reset when the radio flips
                    unique_key = f"a_{j}_{a_action.lower().replace(' ', '_')}"
                    if st.checkbox(agent, value=(a_action == "Select All"), key=unique_key): 
                        selected_agents.append(agent)
                st.markdown('</div>', unsafe_allow_html=True)
            with f_col3:

                st.markdown("#### Status Category")
                all_status = sorted(df_raw["Status"].unique().tolist())
                s_action = st.radio("Status Shortcuts:", ["Select All", "Deselect All"], horizontal=True)
                st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
                selected_status = [] # Make sure this list is initialized right before the loop
                for j, status_type in enumerate(all_status):
                    # ⭐ THE TWEAK: Adding a_action to the key forces a total reset when the radio flips
                    unique_key = f"dc_{j}_{s_action.lower().replace(' ', '_')}"
                    if st.checkbox(status_type, value=(s_action == "Select All"), key=unique_key): 
                        selected_status.append(status_type)
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("#### Global Datetime Bounds")
                valid_times = df_raw["Check-in time_parsed"].dropna()
                min_time = valid_times.min().replace(second=0, microsecond=0).to_pydatetime() if not valid_times.empty else pd.to_datetime("2026-01-01 00:00:00").to_pydatetime()
                max_time = valid_times.max().replace(second=0, microsecond=0).to_pydatetime() if not valid_times.empty else pd.to_datetime("2026-12-31 23:59:00").to_pydatetime()
                if min_time == max_time: max_time += datetime.timedelta(minutes=1)
                start_filter, end_filter = st.slider("Operational window:", min_value=min_time, max_value=max_time, value=(min_time, max_time), format="MM/DD HH:mm")

        ticket_mask = df_raw["Broad Category Group"].isin(selected_items) if filter_mode == "Broad Category Groups (Clean Summary)" else df_raw["Ticket name"].isin(selected_items)
        filtered_df = df_raw[ticket_mask & (df_raw["Check-in by"].isin(selected_agents)) & (df_raw["Status"].isin(selected_status))& (df_raw["Check-in time_parsed"] >= start_filter) & (df_raw["Check-in time_parsed"] <= end_filter)].copy()

        total_rows = len(df_raw)
        status_count = (df_raw["Status"].isin(selected_status)).sum()
        filtered_rows = len(filtered_df)
        st.markdown("### Operational KPIs")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Records", f"{total_rows:,}")
        m2.metric("Total In Status", f"{status_count:,}")
        m3.metric("Total Filtered", f"{filtered_rows:,}")
        st.markdown("---")

    # =========================================================================
    # RENDER SELECTED PAGE SWITCH BLOCKS
    # =========================================================================
    if page_selection == "📋 Live Transaction Ledger":
        st.subheader("Live Operational Records View")
        
        if not is_authenticated:
            st.warning("🔒 Access Denied. Please authenticate via the sidebar panel.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                sort_choice = st.selectbox("Primary Sort Column", options=["Check-in time", "Check-in by", "Ticket name", "Broad Category Group", "ID"])
            with col2:
                sort_order = st.radio("Direction", options=["Ascending ⬆️", "Descending ⬇️"], horizontal=True)
        
            is_ascending = (sort_order == "Ascending ⬆️")
            if sort_choice == "Check-in time":
                filtered_df = filtered_df.sort_values(by="Check-in time_parsed", ascending=is_ascending, na_position="last")
            else:
                filtered_df = filtered_df.sort_values(by=sort_choice, ascending=is_ascending)
                
            display_cols = ["ID", "Order ID", "Confirmation code", "Status", "Attendee first name", "Attendee last name", "Ticket name", "Broad Category Group", "Check-in time", "Check-in by"]
            available_display_cols = [c for c in display_cols if c in filtered_df.columns]
            st.dataframe(filtered_df[available_display_cols], use_container_width=True, hide_index=True)
            #st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            # (...Keep original Page 1 Ledger layout code intact...)


    elif page_selection == "📊 Check-In Analytics Chart":
        st.subheader("Check-In Velocity Timeline")
        
        if not is_authenticated:
            st.warning("🔒 Access Denied. Please authenticate via the sidebar panel.")
        else:
            st.write("Analytics View")
            # (...Keep original Page 2 Charts layout code intact...)
            chart_data = filtered_df[filtered_df["Check-in time_parsed"].notna()].copy()
            if chart_data.empty:
                st.warning("No data matches the selected timeframe bounds or global filter criteria.")
            else:
                c1 = st.columns(1)[0]
                with c1:
                    time_bucket = st.selectbox("Timeline Interval Resolution:", options=["15 Minutes", "30 Minutes", "1 Hour", "Raw Cumulative Total"], index=1)
                
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


    elif page_selection == "🎒 Per-Bag Inventory Audit":
        st.subheader("Global Filter-Bound Performance Reconciliation Ledger")
        if not is_authenticated:
            st.warning("🔒 Access Denied. Input the correct password in the sidebar.")
        elif df_excel_registry.empty:
            st.warning("Could not fetch data from Google Sheet link.")
        else:
            filtered_df = filtered_df.copy()
            filt_agents = sorted(filtered_df["Check-in by"].unique().tolist())
            df_excel_registry = df_excel_registry[df_excel_registry["Name"].isin(filt_agents)]

            filt_bags = sorted(df_excel_registry["Bag Number"].unique().tolist())

            st.markdown("#### Filter Bag Number")
            all_bags = sorted(df_excel_registry["Bag Number"].unique().tolist())
            b_action = st.radio("Bag Shortcuts:", ["Select All", "Deselect All"], horizontal=True)
            st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
            selected_bags = [] # Make sure this list is initialized right before the loop
            for j, bag in enumerate(all_bags):
               # ⭐ THE TWEAK: Adding a_action to the key forces a total reset when the radio flips
               unique_key = f"b_{j}_{b_action.lower().replace(' ', '_')}"
               if st.checkbox(str(bag), value=(b_action == "Select All"), key=unique_key): 
                   selected_bags.append(bag)
            st.markdown('</div>', unsafe_allow_html=True)

            df_excel_registry = df_excel_registry[df_excel_registry["Bag Number"].isin(selected_bags)]
            df_excel_counted = df_excel_counted[df_excel_counted["Bag Number"].isin(selected_bags)]
            
            st.dataframe(df_excel_registry, use_container_width=True, hide_index=True)
            st.dataframe(df_excel_counted, use_container_width=True, hide_index=True)

    # ===================================================
    # NEW PAGE 4: LIVE WORKBAG SHEET ALLOCATION EDITOR (VIA ZAPIER)
    # =========================================================================
    elif page_selection == "📝 Edit Shift Allocations":
        import requests  # Ensure requests is imported at the top of your script if it isn't
        st.subheader("📝 Live Shift & Bag Allocation Editor")
        
        if not is_authenticated:
            st.warning("🔒 Access Denied. Please authenticate via the sidebar panel.")
        elif df_excel_registry.empty:
            st.warning("Database registry is empty or inaccessible.")
        else:
            bag_label = "Bag Number" if "Bag Number" in df_excel_registry.columns else df_excel_registry.columns[0]
            
            st.markdown("#### 🔍 Step 1: Select Record to Modify")
            all_bags_list = sorted(df_excel_registry[bag_label].dropna().unique().tolist())
            selected_bag_to_edit = st.selectbox("Choose a Bag Number / ID:", options=all_bags_list)
             # Fetch target row data
            row_data = df_excel_registry[df_excel_registry[bag_label] == selected_bag_to_edit].iloc[0]
            
            st.subheader(f"Volunteer Name: {row_data.get("Name","none")}")
            st.caption("Write in notes if does not match bag")
            counter_name = st.text_input("Counter:", value=str("Please fill in"))

            st.markdown("---")
            st.markdown(f"#### 🛠️ Step 2: Update Data Fields")
            
            with st.form("zapier_modifier_form"):
                c_meta1, = st.columns(1)
                with c_meta1:
                    notes = st.text_input("Notes", value=str(""))
                
                st.markdown("##### 🎟️ Modify Ticket Quantities Allocations")
                
                meta_cols = [bag_label, "Name", "Notes","Date","Day","Shift Start","Shift End","Gate"]
                meta_cols_existing = [c for c in meta_cols if c in df_excel_registry.columns]
                ticket_cols = [col for col in df_excel_registry.columns if col not in meta_cols_existing]
                
                ticket_inputs = {}
                t_cols_chunks = [ticket_cols[x:x+4] for x in range(0, len(ticket_cols), 4)]
                for chunk in t_cols_chunks:
                    form_cols = st.columns(len(chunk))
                    for idx, t_col in enumerate(chunk):
                        with form_cols[idx]:
                            try: current_qty_val = int(row_data.get(t_col, 0))
                            except: current_qty_val = 0
                            ticket_inputs[t_col] = st.number_input(f"{t_col}:", min_value=0, value=current_qty_val, step=1)
                
                submit_changes = st.form_submit_button("🚀 Send Updates to Zapier")
            
            if submit_changes:
                # Build payload payload explicitly so Zapier receives flat text key pairs
                payload = {
                    "bag_number": str(selected_bag_to_edit),
                    "counter": counter_name,
                    "notes": notes,
                }
                # Merge dynamic numbers directly into payload root
                for ticket_name, qty in ticket_inputs.items():
                    payload[f"ticket_{ticket_name}"] = qty

                with st.spinner("Firing webhook to Zapier..."):
                    try:
                        ZAPIER_HOOK_URL = "https://hooks.zapier.com/hooks/catch/28076615/42ath8o/"
                        response = requests.post(ZAPIER_HOOK_URL, json=payload)
                        
                        if response.status_code in [200, 201]:
                            st.success("🎉 Sent to Zapier! Now go to your Zapier dashboard to test the trigger.")
                        else:
                            st.error(f"Zapier rejected request with status code: {response.status_code}")
                    except Exception as e:
                        st.error(f"Failed to connect to Zapier webhook: {e}")

            # =========================================================================
    # 📝 PAGE 5: AUTOMATED TICKET RE-TITLING & BAG RECONCILIATION ENGINE
    # =========================================================================
    elif page_selection == "📝 TEST":
        st.subheader("📝 Automated Ticket Re-titling & Bag Allocation Engine")
        
        if not is_authenticated:
            st.warning("🔒 Access Denied. Please authenticate via the sidebar panel.")
        elif df_raw.empty:
            st.warning("No live transaction ledger data found to process.")
        else:
            st.markdown("""
            This engine processes all live transactions, **re-titles them** based on your global clustering definitions, 
            calculates total scans per shift window, and sorts the final structured dataset cleanly by **Bag Number**.
            """)
            
            # --- STEP 1: COMPUTE LIVE TRANSACTIONS LOCAL PROCESSING ---
            if True:#with st.spinner("Processing 5,000+ tickets and applying structural mapping rules..."):
                # Work on a copy to preserve raw dashboard data safely
                df_processed = df_raw.copy()
                
                # Filter down to checked-in items only for exact physical count matching
                checked_in_only = df_processed[df_processed["Status"] == "Checked In"].copy()

                if checked_in_only.empty:
                    st.info("No checked-in transactions found to reconcile.")
                    df_reconciled_output = pd.DataFrame()
                else:
                    checked_in_only["Agent_Lower"] = checked_in_only["Check-in by"].str.lower().str.strip()
                    checked_in_only["Ticket_Lower"] = checked_in_only["Ticket name"].str.lower().str.strip()
                    
                    # Identify dynamic ticket columns from your read-only Google Sheet structural template
                    bag_label = "Bag Number" if "Bag Number" in df_excel_registry.columns else (df_excel_registry.columns[0] if not df_excel_registry.empty else "Bag Number")
                    meta_cols = [bag_label, "Gate", "Name", "Shift Start", "Shift End", "Day", "Shift"]
                    meta_cols_existing = [c for c in meta_cols if c in df_excel_registry.columns]
                    ticket_item_columns = [col for col in df_excel_registry.columns if col not in meta_cols_existing] if not df_excel_registry.empty else []
                    
                    cat_lower_map = {cat: cat.lower().strip() for cat in ticket_item_columns}
                    reconciled_rows = []
                    
                    print(df_excel_registry.head())
                    # Loop through your master Google Sheet registry structure to evaluate each bag
                    if not df_excel_registry.empty:
                        for _, row in df_excel_registry.iterrows():
                            day_assigned_str = str(row.get("Day", "")).strip().lower()
                            shift_start_str = str(row.get("Shift Start", "")).strip()
                            shift_end_str = str(row.get("Shift End", "")).strip()
                            
                            # Find calendar date boundaries
                            if day_assigned_str in DAY_TO_DATE_MAPPING:
                                target_calendar_date = pd.to_datetime(DAY_TO_DATE_MAPPING[day_assigned_str]).date()
                            else:
                                target_calendar_date = datetime.date(2025, 7, 5)
                                
                            try:
                                parsed_start_time = pd.to_datetime(shift_start_str, format="%H:%M", errors='coerce').time()
                                if pd.isna(parsed_start_time): parsed_start_time = datetime.time(0, 0)
                            except:
                                parsed_start_time = datetime.time(0, 0)
                                
                            try:
                                parsed_end_time = pd.to_datetime(shift_end_str, format="%H:%M", errors='coerce').time()
                                if pd.isna(parsed_end_time): parsed_end_time = datetime.time(23, 59)
                            except:
                                parsed_end_time = datetime.time(23, 59)
                                
                            bag_shift_datetime_start = datetime.datetime.combine(target_calendar_date, parsed_start_time)
                            bag_shift_datetime_end = datetime.datetime.combine(target_calendar_date, parsed_end_time)
                            if bag_shift_datetime_end < bag_shift_datetime_start:
                                bag_shift_datetime_end += datetime.timedelta(days=1)
                                
                            staff_name_clean = str(row.get("Name", "")).lower().strip()
                            
                            # Isolate scans corresponding strictly to this attendant during their physical shift
                            scans_in_shift = checked_in_only[
                                (checked_in_only["Agent_Lower"] == staff_name_clean) &
                                (checked_in_only["Check-in time_parsed"] >= bag_shift_datetime_start) &
                                (checked_in_only["Check-in time_parsed"] <= bag_shift_datetime_end)
                            ]
                            
                            # Construct the flat dictionary row matching your spreadsheet schema
                            new_row_entry = {
                                "Bag Number": str(row.get(bag_label, "N/A")),
                                "Gate Location": str(row.get("Gate", "N/A")),
                                "Assigned Staff": str(row.get("Name", "N/A")),
                                "Shift Window": f"{shift_start_str} - {shift_end_str}",
                                "Day Assigned": str(row.get("Day", "N/A"))
                            }
                            
                            # Populate re-titled/categorized ticket actual allocation volumes dynamically
                            for category in ticket_item_columns:
                                cat_lower = cat_lower_map[category]
                                # Count scans matching this specific re-titled group definition
                                if not scans_in_shift.empty:
                                    matched_scans = scans_in_shift["Ticket_Lower"].str.contains(cat_lower, na=False).sum()
                                else:
                                    matched_scans = 0
                                    
                                new_row_entry[category] = matched_scans
                                
                            reconciled_rows.append(new_row_entry)
                            
                        df_reconciled_output = pd.DataFrame(reconciled_rows)
                        
                        # --- THE SORT CRITERIA: Enforce explicit numerical/string sorting per Bag Number ---
                        if "Bag Number" in df_reconciled_output.columns:
                            # Safely convert to numeric for natural sort order sorting if bags are digits
                            df_reconciled_output["_sort_key"] = pd.to_numeric(df_reconciled_output["Bag Number"], errors='coerce')
                            df_reconciled_output = df_reconciled_output.sort_values(by=["_sort_key", "Bag Number"]).drop(columns=["_sort_key"])
                    else:
                        df_reconciled_output = pd.DataFrame()

            # --- STEP 2: RENDER GRID INTERFACE ---
            if df_reconciled_output.empty:
                st.warning("⚠️ Ready-to-process target layout sheet template is unavailable.")
            else:
                st.success(f"🎉 Successfully mapped and sorted {len(df_reconciled_output)} Shift Workbags across your operations ledger!")
                
                st.markdown("### 📊 Calculated Operational Summary Sheet Matrix")
                st.caption("You can inspect values or make direct overrides in the editable cells below before saving:")
                
                # Render interactive high-speed spreadsheet editor framework
                final_edited_df = st.data_editor(df_reconciled_output, use_container_width=True, hide_index=True)
                
                # Build seamless down-stream downloadable object memory buffer 
                csv_payload = final_edited_df.to_csv(index=False).encode('utf-8')
                
                st.markdown("---")
                st.markdown("#### 📥 Step 3: Save directly to Google Sheets")
                st.info("💡 **How to update Google Sheets in 5 seconds without cloud credentials:** Click the download button below, open your destination Google Sheet, click **File > Import > Upload**, and drag this file directly in to overwrite the layout!")
                
                st.download_button(
                    label="📥 Download Sorted Reconciled Matrix (CSV)",
                    data=csv_payload,
                    file_name=f"sorted_bag_allocations_{datetime.date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )