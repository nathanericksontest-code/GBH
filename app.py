import streamlit as st
import pandas as pd
import json
import os
import datetime
import plotly.express as px
#from google.oauth2 import service_account
#import gspread
from dotenv import load_dotenv
import requests
import webscrape
import asyncio
import base64

st.set_page_config(page_title="Gate Operations Control", layout="wide")


# =========================================================================
# 🔐 GOOGLE SHEETS & ACCESS SECURITY SETTINGS
# =========================================================================

load_dotenv()


try:
    GOOGLE_SHEET_COUNTER_URL = os.environ.get("GOOGLE_SHEET_COUNTER_URL")
    GOOGLE_SHEET_PREPACK_URL = os.environ.get("GOOGLE_SHEET_PREPACK_URL")
    GOOGLE_SHEET_EXTRAS_URL = os.environ.get("GOOGLE_SHEET_EXTRAS_URL")
    GOOGLE_SHEET_AUDITOR_URL = os.environ.get("GOOGLE_SHEET_AUDITOR_URL")
    APP_PASSWORD = os.environ.get("APP_PASSWORD")
    raw_columns = os.environ.get("TICKET_COLUMNS")
    TICKET_COLUMNS = json.loads(raw_columns)
    DAY_TO_DATE_MAPPING = os.environ.get("DAY_TO_DATE_MAPPING")
    ZAPIER_AUDITOR_HOOK_URL = os.environ.get("ZAPIER_AUDITOR_HOOK_URL")
    ZAPIER_COUNTER_HOOK_URL = os.environ.get("ZAPIER_COUNTER_HOOK_URL")
    ZAPIER_EXTRAS_HOOK_URL = os.environ.get("ZAPIER_EXTRAS_HOOK_URL")
except:
    GOOGLE_SHEET_COUNTER_URL = st.secrets.get("GOOGLE_SHEET_COUNTER_URL")
    GOOGLE_SHEET_PREPACK_URL = st.secrets.get("GOOGLE_SHEET_PREPACK_URL")
    GOOGLE_SHEET_EXTRAS_URL = st.secrets.get("GOOGLE_SHEET_EXTRAS_URL")
    GOOGLE_SHEET_AUDITOR_URL = st.secrets.get("GOOGLE_SHEET_AUDITOR_URL")
    APP_PASSWORD = st.secrets.get("APP_PASSWORD")
    TICKET_COLUMNS = st.secrets.get("TICKET_COLUMNS")
    DAY_TO_DATE_MAPPING = st.secrets.get("DAY_TO_DATE_MAPPING")
    ZAPIER_AUDITOR_HOOK_URL = st.secrets["ZAPIER_AUDITOR_HOOK_URL"]
    ZAPIER_COUNTER_HOOK_URL = st.secrets["ZAPIER_COUNTER_HOOK_URL"]
    ZAPIER_EXTRAS_HOOK_URL = st.secrets["ZAPIER_EXTRAS_HOOK_URL"]


# 1. Create a single cached resource that acts as our global storage container
@st.cache_resource
def get_global_store():
    # This returns a standard, mutable dictionary that persists across all sessions
    return {"global_df": None, "current_version":None}

# 2. Initialize the global store
global_store = get_global_store()

def single_click_pipeline():
    # Streamlit requires a visual placeholder because spinners don't auto-render 
    # inside download button callbacks natively
    status_text = st.empty()
    status_text.info("🚀 Launching browser automation & extracting live data...")
    
    try:
        # 1. Fire off the playwright script
        file_path = asyncio.run(webscrape.automated_data_extraction())
        
        if file_path:
            # 2. Read the file content immediately into memory
            with open(file_path, "rb") as f:
                csv_bytes = f.read()
            
            status_text.success("✨ Success! File sent to your browser downloads.")
            return csv_bytes
        else:
            status_text.error("Extraction failed.")
            return b""
            
    except Exception as e:
        status_text.error(f"Error: {str(e)}")
        return b""



# 3. Helper function to read the current global data
def get_global_data():
    # If no admin has uploaded a file yet, load your default data
    if global_store["global_df"] is None:
        return pd.DataFrame()
    return global_store["global_df"]

@st.cache_data(ttl=10)
def load_evt_data(df):
    # if not os.path.exists(LIVE_DATA_FILE):
    #     return pd.DataFrame(columns=["Check-in time_parsed", "Check-in Day Name", "Check-in by", "Ticket name", "Status"])
    # with open(LIVE_DATA_FILE, "r", encoding="utf-8") as f:
    #     data = json.load(f)
    # df = pd.DataFrame(data)
    # df.columns = df.columns.str.strip()
    
    if "Check-in time" in df.columns:
        df["Check-in time_parsed"] = pd.to_datetime(df["Check-in time"].str.strip(), format="%b %d, %Y %I:%M %p", errors="coerce")
        df["Check-in Day Name"] = df["Check-in time_parsed"].dt.day_name().str.strip().str.lower()
    else:
        df["Check-in time_parsed"] = pd.NaT
        df["Check-in Day Name"] = ""
    return df

def run_zapier(df_zap,destination):
    
    if destination == "Counted":
        sheet_ID = 1555218451
        min_val = 0
        step_size = 1
    elif destination == "Extras":
        sheet_ID = 807176535
        min_val = -100
        step_size = 10
    elif destination == "Auditor":
        sheet_ID = 1901971005
        min_val = -100
        step_size = 1


    #bag_label = "Bag Number" if "Bag Number" in df_zap.columns else df_zap.columns[0]
    
    st.markdown("#### 🔍 Step 1: Select Record to Modify")

    # Get clean options list
    all_bags_list = sorted(df_zap[bag_label].dropna().unique().tolist())

    # 1. Use columns to pull the selectbox, name, and input onto a single compact row
    col1, col2, col3 = st.columns([1.2, 1.5, 1.3])

    with col1:
        selected_bag_to_edit = st.selectbox(
            "Bag Number / ID:",  # Shortened label to save vertical space
            options=all_bags_list,
            key=f"{destination}_selectbox"
        )

    # Fetch target row data safely
    row_data = df_zap[df_zap[bag_label] == selected_bag_to_edit].iloc[0]
    volunteer_name = row_data.get("Name", "none")

    with col2:
        # Use standard markdown instead of subheader to drop the large padding blocks
        st.markdown(f"**Volunteer Name:**\n### {volunteer_name}")
        st.caption("📝 Write in notes if mismatch occurs")

    with col3:
        counter_name = st.text_input(
            "Counter Staff Assignment:", 
            value="Please fill in", 
            key=f"{destination}_counter"
        )

    # 2. Tightened transition directly into Step 2 (Removed the heavy st.markdown("---") rule line)
    st.markdown(f"#### 🛠️ Step 2: Update Data Fields")
    # st.markdown("#### 🔍 Step 1: Select Record to Modify")
    # all_bags_list = sorted(df_zap[bag_label].dropna().unique().tolist())
    # selected_bag_to_edit = st.selectbox("Choose a Bag Number / ID:", options=all_bags_list,key=f"{destination}_selectbox")
    #     # Fetch target row data
    # row_data = df_zap[df_zap[bag_label] == selected_bag_to_edit].iloc[0]
    
    # st.subheader(f"Volunteer Name: {row_data.get("Name","none")}")
    # st.caption("Write in notes if does not match bag")
    # counter_name = st.text_input("Counter:", value=str("Please fill in"), key=f"{destination}_counter")

    # st.markdown("---")
    # st.markdown(f"#### 🛠️ Step 2: Update Data Fields")
    
    with st.form(f"{destination}_form"):
        c_meta1, = st.columns(1)
        with c_meta1:
            notes = st.text_input("Notes", value=row_data.get("Notes",""))
        
        st.markdown("##### 🎟️ Modify Ticket Quantities Allocations")
        
        meta_cols = [bag_label, "Name", "Notes","Date","Day","Shift Start","Shift End","Gate"]
        meta_cols_existing = [c for c in meta_cols if c in df_excel_counted.columns]
        ticket_cols = TICKET_COLUMNS

        ticket_inputs = {}
        t_cols_chunks = [ticket_cols[x:x+4] for x in range(0, len(ticket_cols), 4)]
        for chunk in t_cols_chunks:
            form_cols = st.columns(len(chunk))
            for idx, t_col in enumerate(chunk):
                with form_cols[idx]:
                    try: current_qty_val = int(row_data.get(t_col, 0))
                    except: current_qty_val = 0
                    ticket_inputs[t_col] = st.number_input(f"{t_col}:", min_value=min_val, value=current_qty_val, step=step_size)
        
        submit_changes = st.form_submit_button("🚀 Send Updates to Database", key=f"{destination}_submit_btn")
    
    if submit_changes:
        # Build payload payload explicitly so Zapier receives flat text key pairs
        

        payload = {
            "bag_number": str(selected_bag_to_edit),
            "counter": counter_name,
            "notes": notes,
            "worksheet": sheet_ID
        }
        # Merge dynamic numbers directly into payload root
        for ticket_name, qty in ticket_inputs.items():
            payload[f"ticket_{ticket_name}"] = qty

        with st.spinner("Firing webhook to Database..."):
            try:
                response = requests.post(ZAPIER_COUNTER_HOOK_URL, json=payload)
                
                if response.status_code in [200, 201]:
                    st.success("🎉 Sent to Database! Enter next bag.")
                else:
                    st.error(f"Zapier rejected request with status code: {response.status_code}")
            except Exception as e:
                st.error(f"Failed to connect to Zapier webhook: {e}")


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
    ### LABELS
    name_lower = str(name).lower()
    if "meals" in name_lower:
        return "Meals"
    elif "weekend" in name_lower:
        return "Weekend"
    elif "green lot" in name_lower:
        return "Green Lot"
    elif "blue lot" in name_lower:
        return "Blue Lot"
    elif "purple lot" in name_lower:
        return "Purple Lot"
    elif "orange lot" in name_lower:
        return "Orange Lot"
    elif "red lot" in name_lower:
        return "Red Lot"
    elif "vendor green lot" in name_lower:
        return "Vendor Parking"
    elif "multi color" in name_lower:
        return "Multiguest Parking"
    elif "white" in name_lower:
        return "Guest Parking"
    elif "all access" in name_lower or "all-access" in name_lower:
        return "All-Access"
    elif "saturday" in name_lower:
        return "Saturday"
    elif "sunday camping" in name_lower:
        return "Sunday Camping"
    elif "sunday" in name_lower:
        return "Sunday"
    elif "upgrade" in name_lower:
        return "Upgrades"
    else:
        print("Unknown ticket type")
        return "Unknown"

# --- SIDEBAR NAVIGATION (NOW FEATURING 4 PAGES) ---
st.sidebar.title("Navigation Dashboard")


# Your existing radio component
page_selection = st.sidebar.radio(
    "Go to view:",
    options=[
        "📋 Live Transaction Ledger",
        "📊 Check-In Analytics Chart",
        "🎒 Per-Bag Inventory Audit",
        "📝 Count Stuff Out",
        "📝 TEST"
    ],
    key="navigation_dashboard"
)
st.sidebar.markdown("---")

# =========================================================================
# 🔒 PASSWORD PROTECTION GATE (Applies to all pages)
# =========================================================================
is_authenticated = False
#if page_selection in ["🎒 Per-Bag Inventory Audit", "📝 Count Stuff Out"]:
st.sidebar.subheader("🔒 Authentication Required")
user_password = st.sidebar.text_input("Enter Inventory Access Password:", type="password")
if user_password == APP_PASSWORD:
    st.sidebar.success("Access Granted!")
    is_authenticated = True
else:
    if user_password != "": st.sidebar.error("Incorrect Password")
    is_authenticated = False

st.sidebar.markdown("---")



# Fetch fresh copy from the cloud if authenticated
any_page = ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart", "🎒 Per-Bag Inventory Audit", "📝 Count Stuff Out", "📝 TEST"]
if is_authenticated:
    #st.sidebar.markdown("## ⬇️ Download Raw Data")
    st.sidebar.markdown("## 🔄 Global Data Sync")
    filename_placeholder = st.sidebar.empty()
    # The Single Button Approach: Passing the function directly to the data argument

    # A normal button does NOT run on page load. It stays completely idle.
    if st.sidebar.button("⬇️ Download Tickets CSV"):
        
        # 1. Create a status container so the user sees live progress updates
        status = st.empty()
        status.info("🚀 Launching scraper background thread... (This will take a couple of minutes)")
        
        try:
            # 2. Run the heavy automation script
            file_path = asyncio.run(webscrape.automated_data_extraction())
            
            if file_path and os.path.exists(file_path):
                status.info("📦 Packaging data for browser download...")
                
                # 3. Read the generated file into a base64 text string
                with open(file_path, "rb") as f:
                    csv_bytes = f.read()
                filename = os.path.basename(file_path)
                b64_data = base64.b64encode(csv_bytes).decode()
                
                # Clean up the cloud server storage immediately
                os.remove(file_path)
                
                # 4. Use a clean HTML snippet that embeds the file directly into the page.
                # Setting 'target="_self"' tells the browser to process it instantly without a popup blocker.
                components_html = f"""
                <div style="text-align: center; margin-top: 10px;">
                    <p style="color: #28a745; font-weight: bold; font-family: sans-serif;">✨ Extraction Complete! Fetching file...</p>
                    <iframe src="data:text/csv;base64,{b64_data}" download="{filename}" style="display:none;" sandbox="allow-downloads"></iframe>
                    <script>
                        // Fallback to force download if iframe loading is restricted by browser policy
                        var a = document.createElement('a');
                        a.href = 'data:text/csv;base64,{b64_data}';
                        a.download = '{filename}';
                        a.click();
                    </script>
                </div>
                """
                
                # Inject the download stream directly into the UI session
                st.components.v1.html(components_html, height=80)
                status.empty() # Clear out the loading notice
                
            else:
                status.error("Automation completed, but no file was found on the server.")
                
        except Exception as e:
            status.error(f"Extraction failed: {str(e)}")



    #st.sidebar.markdown("## 🔄 Global Data Sync")
    uploaded_file = st.sidebar.file_uploader("Upload latest CSV", type=["csv"], key="internal_sync")

    if uploaded_file is not None:
        if st.sidebar.button("🚀 Sync Globally for EVERYONE"):
            # Overwrite the global memory dictionary value
            global_store["global_df"] = pd.read_csv(uploaded_file,index_col=False)
            global_store["current_version"] = uploaded_file.name

            # Clear Streamlit's UI cache so every active user drops old metrics 
            # and pulls the fresh dataframe from global_store instantly
            st.cache_data.clear()
            st.sidebar.success("🎉 Data updated for all users on the server!")
            # Force overwrite the global memory space

    # 2. Every user viewing the app pulls from the exact same in-memory object
    df_raw = get_global_data()
    if not df_raw.empty:
        filename_placeholder.markdown(f"Last uploaded version: {global_store['current_version']}")

    df_raw = load_evt_data(df_raw)

if is_authenticated and page_selection in ["🎒 Per-Bag Inventory Audit", "📝 Count Stuff Out","📝 TEST"]:
    df_excel_registry = load_google_sheet_inventory(GOOGLE_SHEET_PREPACK_URL)
    df_excel_counted = load_google_sheet_inventory(GOOGLE_SHEET_COUNTER_URL)
    df_excel_extras = load_google_sheet_inventory(GOOGLE_SHEET_EXTRAS_URL)
    df_excel_audit = load_google_sheet_inventory(GOOGLE_SHEET_AUDITOR_URL)
else:
    st.session_state.download_file_path = ""
    st.session_state.adjustment_df = pd.DataFrame()
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

                #st.markdown("#### Global Datetime Bounds")
                #valid_times = df_raw["Check-in time_parsed"].dropna()
                #min_time = valid_times.min().replace(second=0, microsecond=0).to_pydatetime() if not valid_times.empty else pd.to_datetime("2025-01-01 00:00:00").to_pydatetime()
                #max_time = valid_times.max().replace(second=0, microsecond=0).to_pydatetime() if not valid_times.empty else pd.to_datetime("2026-12-31 23:59:00").to_pydatetime()
                #if min_time == max_time: max_time += datetime.timedelta(minutes=1)
                #start_filter, end_filter = st.slider("Operational window:", min_value=min_time, max_value=max_time, value=(min_time, max_time), format="MM/DD HH:mm")

            ticket_mask = df_raw["Broad Category Group"].isin(selected_items) if filter_mode == "Broad Category Groups (Clean Summary)" else df_raw["Ticket name"].isin(selected_items)
            filtered_df = df_raw[ticket_mask & (df_raw["Check-in by"].isin(selected_agents)) & (df_raw["Status"].isin(selected_status))].copy() #& (df_raw["Check-in time_parsed"] >= start_filter) & (df_raw["Check-in time_parsed"] <= end_filter)
            
            total_count = len(df_raw)
            status_count = (df_raw["Status"].isin(selected_status)).sum()
            filtered_count = len(filtered_df)
            st.markdown("### Operational KPIs")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Records", f"{total_count:,}")
            m2.metric("Total In Status", f"{status_count:,}")
            m3.metric("Total Filtered", f"{filtered_count:,}")
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
                sort_choice = st.selectbox("Primary Sort Column", options=["Check-in time", "Check-in by", "Ticket name", "Broad Category Group"])
            with col2:
                sort_order = st.radio("Direction", options=["Ascending ⬆️", "Descending ⬇️"], horizontal=True)
        
            is_ascending = (sort_order == "Ascending ⬆️")
            if sort_choice == "Check-in time":
                filtered_df = filtered_df.sort_values(by="Check-in time_parsed", ascending=is_ascending, na_position="last")
            else:
                filtered_df = filtered_df.sort_values(by=sort_choice, ascending=is_ascending)
                
            display_cols = ["ID", "Status", "Attendee first name", "Attendee last name", "Ticket name", "Broad Category Group", "Check-in time", "Check-in by","Refunded by","Refund date"]
            available_display_cols = [c for c in display_cols if c in filtered_df.columns]
            st.dataframe(filtered_df[available_display_cols], width='stretch', hide_index=True)
            
            if not df_raw.empty:
                # 1. Filter down to successful check-ins only
                df_checked_in = df_raw[df_raw["Status"] == "Checked In"].copy()
                
                if not df_checked_in.empty:
                    # 2. Ensure timestamps are formatted uniformly into readable string windows
                    df_checked_in["Check-In Time"] = df_checked_in["Check-in time_parsed"].dt.strftime("%Y-%m-%d %I:%M %p")
                    
                    # 3. Create your cross-tabulation (Pivot Table) counting categories
                    # This automatically places your unique categories as horizontal columns!
                    df_pivot = pd.crosstab(
                        index=[df_checked_in["Check-In Time"], df_checked_in["Check-in by"]],
                        columns=df_checked_in["Broad Category Group"]
                    ).reset_index()
                    
                    # 4. Clean up the naming of the column index headers
                    df_pivot.columns.name = None
                    
                    # 5. Dynamic Column Alignment Map: Align with the Counted table structure
                    # Ensure all columns exist even if no one checked into them during that minute frame
                    target_columns = TICKET_COLUMNS
                    
                    for col in target_columns:
                        if col not in df_pivot.columns:
                            df_pivot[col] = 0 # Initialize empty column if missing
                            
                    # 6. Re-order cleanly to match your precise user interface layout
                    final_cols_order = ["Check-In Time", "Check-in by"] + target_columns
                    # Filter down only to columns that we explicitly want to display
                    df_final_matrix = df_pivot[[c for c in final_cols_order if c in df_pivot.columns]]
                    
                    # 7. Sort Chronologically (Newest check-ins at the top)
                    df_final_matrix = df_final_matrix.sort_values(by="Check-In Time", ascending=False)
                    
                    # Display the result table
                    st.dataframe(df_final_matrix, width='stretch', hide_index=True)
                else:
                    st.info("No active 'Checked In' transactions found matching your filtering parameters.")
            else:
                st.warning("Eventeny live transaction data ledger is currently unavailable.")
           


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
                st.plotly_chart(fig, width='stretch')





    #################################
    ######## Audit Page ###########
    #################################
    elif page_selection == "🎒 Per-Bag Inventory Audit":

        if not is_authenticated:
            st.warning("🔒 Access Denied. Input the correct password in the sidebar.")
        elif df_excel_registry.empty:
            st.warning("Could not fetch data from Google Sheet link.")
        else:
            filtered_df = filtered_df.copy()
            filt_agents = sorted(filtered_df["Check-in by"].unique().tolist())
            df_excel_registry = df_excel_registry[df_excel_registry["Name"].isin(filt_agents)]

            filt_bags = sorted(df_excel_registry["Bag Number"].unique().tolist())

            with st.expander("GBH PrePack Filter", expanded=False):
                st.markdown("#### Filter Bag Number")
                all_bags = sorted(df_excel_registry["Bag Number"].unique().tolist())
                b_action = st.radio("Bag Shortcuts:", ["Select All", "Deselect All"], horizontal=True)
                st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
                selected_bags = [] # Make sure this list is initialized right before the loop
                for j, bag in enumerate(all_bags):
                    unique_key = f"b_{j}_{b_action.lower().replace(' ', '_')}"
                    current_row = df_excel_registry[df_excel_registry["Bag Number"] == bag]
                    
                    # Safety Check: Make sure the row isn't empty before trying to index into it
                    if not current_row.empty:
                        # Extract the raw scalar values using .iloc[0]
                        start_dt = current_row["Start Date"].iloc[0]
                        start_tm = current_row["Shift Start"].iloc[0]
                        end_dt   = current_row["End Date"].iloc[0]
                        end_tm   = current_row["Shift End"].iloc[0]
                        name     = current_row["Name"].iloc[0]
                        
                        # Format the label text cleanly
                        label_text = f"{str(bag)} {name}: {start_tm} {start_dt} - {end_tm} {end_dt}"
                        
                        if st.checkbox(label_text, value=(b_action == "Select All"), key=unique_key): 
                            selected_bags.append(bag)
                st.markdown('</div>', unsafe_allow_html=True)

            df_excel_registry = df_excel_registry[df_excel_registry["Bag Number"].isin(selected_bags)]
            df_excel_counted = df_excel_counted[df_excel_counted["Bag Number"].isin(selected_bags)]
            
            # How many tickets were found that could be attributed to a check in person?
            bag_agents = sorted(df_excel_registry["Name"].unique().tolist())
            df_lim_filtered = filtered_df[filtered_df["Check-in by"].isin(bag_agents)]

            count_in_people_with_bags = len(df_lim_filtered)
            st.markdown("### Eventeny to GBH Database")
            m1, m2 = st.columns(2)
            m1.metric("Number Attributed to People with PrePack Bag: ", f"{count_in_people_with_bags:,}")
            m2.metric("Number With no Matching Name: ", f"{(filtered_count-count_in_people_with_bags):,}")
            
                #################################
             ######## PrePack ###########
                #################################
            st.markdown("### PrePack")
            st.dataframe(df_excel_registry, width='stretch', hide_index=True)
            
            with st.expander("Eventeny Filtered Transactions", expanded=False):
                st.markdown("### Eventeny")
                # display_cols = ["ID", "Status", "Attendee first name", "Attendee last name", "Ticket name", "Broad Category Group", "Check-in time", "Check-in by"]
                #             available_display_cols = [c for c in display_cols if c in filtered_df.columns]
                #             st.dataframe(df_lim_filtered[available_display_cols], width='stretch', hide_index=True)
                #             st.markdown("### 📊 Consolidated Ticket Check-In Log Matrix")

                if not df_lim_filtered.empty:
                    # 1. Filter down to successful check-ins only
                    df_checked_in_sums =df_lim_filtered.copy()

                    if not df_checked_in_sums.empty:
                        # 2. Ensure timestamps are formatted uniformly into readable string windows
                        df_checked_in_sums["Check-In Time"] = df_checked_in_sums["Check-in time_parsed"].dt.strftime("%Y-%m-%d %I:%M %p")
                        
                        # 3. Create your cross-tabulation (Pivot Table) counting categories
                        # This automatically places your unique categories as horizontal columns!
                        df_pivot_sums = pd.crosstab(
                            index=[df_checked_in_sums["Check-In Time"], df_checked_in_sums["Check-in by"]],
                            columns=df_checked_in_sums["Broad Category Group"]
                        ).reset_index()
                        
                        # 4. Clean up the naming of the column index headers
                        df_pivot_sums.columns.name = None
                        
                        # 5. Dynamic Column Alignment Map: Align with the Counted table structure
                        # Ensure all columns exist even if no one checked into them during that minute frame
                        target_columns = TICKET_COLUMNS
                        
                        for col in target_columns:
                            if col not in df_pivot_sums.columns:
                                df_pivot_sums[col] = 0 # Initialize empty column if missing
                                
                        # 6. Re-order cleanly to match your precise user interface layout
                        final_cols_order = ["Check-In Time", "Check-in by"] + target_columns
                        # Filter down only to columns that we explicitly want to display
                        df_final_matrix = df_pivot_sums[[c for c in final_cols_order if c in df_pivot_sums.columns]]
                        
                        # 7. Sort Chronologically (Newest check-ins at the top)
                        df_final_matrix = df_final_matrix.sort_values(by="Check-In Time", ascending=False)
                        
                        # Display the result table
                        st.dataframe(df_final_matrix, width='stretch', hide_index=True)
                    else:
                        st.info("No active 'Checked In' transactions found matching your filtering parameters.")
                else:
                    st.warning("Eventeny live transaction data ledger is currently unavailable.")
            
                #################################
             ######## SHIFT BOUNDED EVENTENY ###########
                #################################
            st.markdown("### 🕒 Shift-Bounded Eventeny Scan Totals")

            if not df_raw.empty and not df_excel_registry.empty:
                with st.spinner("Calculating scan totals..."):
                    df_scans = df_lim_filtered.copy()
                    df_shifts = df_excel_registry.copy()
                    
                    df_scans["Agent_Lower"] = df_scans["Check-in by"].str.lower().str.strip()
                    df_shifts["Name_Lower"] = df_shifts["Name"].str.lower().str.strip()
                    
                    # Track the index of every scan that successfully matches a shift window
                    matched_scan_indices = set()
                    
                    meta_cols = ["Bag Number", "Gate", "Name", "Shift Start", "Start Date", "Shift End", "End Date", "Day", "Shift", "Name_Lower"]
                    ticket_cols = [col for col in df_shifts.columns if col not in meta_cols]
                    
                    bounded_shift_summary = []
                    
                    # 1. First Pass: Process all scheduled shifts normally
                    for _, shift_row in df_shifts.iterrows():
                        staff_member = shift_row.get("Name_Lower", "")
                        bag_id = str(shift_row.get("Bag Number", "N/A"))
                        
                        if pd.isna(shift_row.get("Name")) or staff_member == "":
                            continue
                            
                        start_datetime_str = f"{shift_row.get('Start Date')} {shift_row.get('Shift Start')}"
                        end_datetime_str = f"{shift_row.get('End Date')} {shift_row.get('Shift End')}"
                        
                        shift_start_dt = pd.to_datetime(start_datetime_str, errors='coerce')
                        shift_end_dt = pd.to_datetime(end_datetime_str, errors='coerce')
                        
                        if pd.isna(shift_start_dt) or pd.isna(shift_end_dt):
                            continue
                        
                        # Isolate scans for this agent in this specific window
                        scans_in_window = df_scans[
                            (df_scans["Agent_Lower"] == staff_member) &
                            (df_scans["Check-in time_parsed"] >= shift_start_dt) &
                            (df_scans["Check-in time_parsed"] <= shift_end_dt)
                        ]
                        
                        # Remember these scans so we don't double-count them later
                        matched_scan_indices.update(scans_in_window.index.tolist())
                        
                        summary_entry = {
                            "Bag Number": bag_id,
                            "Name": shift_row.get("Name"),
                            "Shift Bounds": f"{start_datetime_str} - {end_datetime_str}"
                        }
                        
                        # Exact column match fix applied here too
                        for ticket_type in ticket_cols:
                            if not scans_in_window.empty:
                                matched_sum = (scans_in_window["Broad Category Group"].str.lower().str.strip() == ticket_type.lower().strip()).sum()
                            else:
                                matched_sum = 0
                            summary_entry[ticket_type] = matched_sum
                            
                        bounded_shift_summary.append(summary_entry)
                        
                    # 2. Second Pass: Find all scans that FAILED to match any time window
                    all_unassigned_scans = df_scans[~df_scans.index.isin(matched_scan_indices)]
                    
                    # Group the leftovers by agent name so we can give each agent their own catch-all row
                    if not all_unassigned_scans.empty:
                        unique_failed_agents = all_unassigned_scans["Check-in by"].unique()
                        
                        for agent in unique_failed_agents:
                            agent_leftovers = all_unassigned_scans[all_unassigned_scans["Check-in by"] == agent]
                            
                            # Create a special fallback row design
                            leftover_entry = {
                                "Bag Number": f"⚠️{agent}",
                                "Name": agent,
                                "Shift Bounds": "Outside Scheduled Hours"
                            }
                            
                            for ticket_type in ticket_cols:
                                matched_sum = (agent_leftovers["Broad Category Group"].str.lower().str.strip() == ticket_type.lower().strip()).sum()
                                leftover_entry[ticket_type] = matched_sum
                                
                            bounded_shift_summary.append(leftover_entry)

                    # 3. Render and format the final DataFrame
                    if bounded_shift_summary:
                        df_bounded_output = pd.DataFrame(bounded_shift_summary)
                        
                        # Sort trick: Put true bags first numerically, and push the "⚠️ OUT-OF-BOUNDS" rows to the very bottom
                        df_bounded_output["_sort"] = pd.to_numeric(df_bounded_output["Bag Number"], errors='coerce')
                        # Give the out-of-bounds rows an artificially high sort number so they sink to the bottom
                        df_bounded_output["_sort"] = df_bounded_output["_sort"].fillna(999999) 
                        
                        df_bounded_output = df_bounded_output.sort_values(by=["_sort", "Name"]).drop(columns=["_sort"])
                        
                        st.dataframe(df_bounded_output, width='stretch', hide_index=True)
                    else:
                        st.info("No data available.")
                    
                    grand_total = df_bounded_output[ticket_cols].sum().sum()
            

                st.markdown("---")
                # Displays a prominent KPI card displaying your overall total cleanly
                m1, m2 = st.columns(2)
                m1.metric(label="📊 Grand Total Eventeny Tickets Accounted For", value=int(grand_total))
                m2.metric("Number With Unidentified Ticket Type: ", f"{(count_in_people_with_bags-grand_total):,}")
                
                # Optional: Display a small itemized markdown list breaking down the counts per column
                itemized_breakdown = ", ".join([f"**{col}**: {int(df_bounded_output[col].sum())}" for col in ticket_cols if df_bounded_output[col].sum() > 0])
                st.markdown(f"**Itemized Scan Breakdown:** {itemized_breakdown}")


                #################################
             ######## COUNTED ###########
                #################################
            st.markdown("### Counted")
            st.dataframe(df_excel_counted, width='stretch', hide_index=True)
            

            ######## AUDITOR ADJUSTMENTS ###########

            with st.expander("Auditor Adjustments"):
                with st.expander("Re-count"):
                    run_zapier(df_excel_counted.copy(), "Counted")
                with st.expander("Extras"):
                    run_zapier(df_excel_extras.copy(), "Extras")
                with st.expander("Edits"):
                    run_zapier(df_excel_audit.copy(), "Auditor")

            #all_bags = sorted(df_excel_counted["Bag Number"].unique().tolist())
            # if "wide_adjustment_df" not in st.session_state:
            #     # Create the base dictionary template
            #     template_data = {"Bag Number": all_bags}
                
            #     # Initialize every ticket type column with zeros
            #     for ticket in TICKET_COLUMNS:
            #         template_data[ticket] = [0] * len(all_bags)
                    
            #     df_template_data = pd.DataFrame(template_data)
            # else:
            #     df_template_data = st.session_state.wide_adjustment_df.copy()

            # st.markdown("#### Input Corrections")
            # st.caption("Double-click any cell to input adjustments directly into the matrix.")

            # # 3. Render the interactive wide table matrix
            # edited_matrix = st.data_editor(
            #     df_template_data,
            #     disabled=["Bag Number"], # Lock down only the bag numbers so they remain as clean row labels
            #     hide_index=True,
            #     use_container_width=True,
            #     key="wide_bulk_editor"
            # )

            # # 4. Handle Save & Submit
            # if st.button("📤 Submit Adjustments", type="primary"):
            #     st.session_state.wide_adjustment_df = edited_matrix.copy()
            #     st.success("🎉 Matrix adjustments committed successfully!")



                #################################
             ######## Results ###########
                #################################
            st.markdown("### Audit")
            st.markdown("###### Negative values indicate missing wristbands/stickers")
            ticket_cols = TICKET_COLUMNS
            # Ensure we have valid, matching datasets to perform math on
            if not df_excel_registry.empty and not df_excel_counted.empty:
                # 1. Standardize Bag Number column handling string/numeric quirks
                df_pre = df_excel_registry.copy()
                df_cnt = df_excel_counted.copy()
                df_evt = df_bounded_output.copy()
                df_ext = df_excel_extras.copy()
                df_aud = df_excel_audit.copy()
                
                df_pre["Bag Number"] = df_pre["Bag Number"].astype(str).str.strip()
                df_cnt["Bag Number"] = df_cnt["Bag Number"].astype(str).str.strip()
                df_evt["Bag Number"] = df_evt["Bag Number"].astype(str).str.strip()
                df_aud["Bag Number"] = df_aud["Bag Number"].astype(str).str.strip()
                df_ext["Bag Number"] = df_ext["Bag Number"].astype(str).str.strip()
                
                # 2. Extract and align dataframes by setting Bag Number as the layout index
                # Only pull ticket columns that actually exist in both sheets to prevent NaN crashes
                valid_cols = [col for col in ticket_cols if col in df_pre.columns and col in df_evt.columns and col in df_cnt.columns and col in df_aud.columns]
                
                if valid_cols:
                    pre_matrix = df_pre.set_index("Bag Number")[valid_cols].fillna(0).astype(int)
                    cnt_matrix = df_cnt.set_index("Bag Number")[valid_cols].fillna(0).astype(int)
                    evt_matrix = df_evt.set_index("Bag Number")[valid_cols].fillna(0).astype(int)
                    aud_matrix = df_aud.set_index("Bag Number")[valid_cols].fillna(0).astype(int)
                    ext_matrix = df_ext.set_index("Bag Number")[valid_cols].fillna(0).astype(int)


                    # 3. Align both frames completely on matching Bag Numbers
                    # This keeps all bags from both sheets and aligns their structures
                    all_bags = sorted(list(set(cnt_matrix.index)))
                    pre_matrix = pre_matrix.reindex(all_bags, fill_value=0)
                    cnt_matrix = cnt_matrix.reindex(all_bags, fill_value=0)
                    evt_matrix = evt_matrix.reindex(all_bags, fill_value=0)
                    aud_matrix = aud_matrix.reindex(all_bags, fill_value=0)
                    ext_matrix = ext_matrix.reindex(all_bags, fill_value=0)

                    # 4. Perform math subtraction (Negative means missing)
                    audit_matrix = cnt_matrix + evt_matrix - aud_matrix - pre_matrix - ext_matrix 
                    
                    # 5. Format it back into a beautiful UI dataframe view
                    df_audit = audit_matrix.reset_index()

                    # ⭐ THE ADDITION: Calculate row-wise sum for all columns from index 1 to the end
                    # (Since index 0 is 'Bag Number', columns 1 to the end are your ticket counts)
                    row_totals = df_audit.iloc[:, 1:].sum(axis=1)
                    red_lot_exemption = df_audit["Red Lot"]
                    kids_exemption = df_audit["Kids"]
                    row_totals = row_totals - red_lot_exemption - kids_exemption

                    # Inject the "Total Discrepancy" column cleanly at position 1 (Column 2)
                    df_audit.insert(1, "Total Discrepancy", row_totals)
                    
                    df_audit[df_audit.columns[0]] = pd.to_numeric(df_audit[df_audit.columns[0]], errors='coerce')
                    # ⭐ THE ADDITION: Sort primarily by Total Discrepancy (Largest first)
                    # and secondarily by Bag Number (Smallest/Alpha first)
                    df_audit = df_audit.sort_values(
                        by=["Total Discrepancy", df_audit.columns[0]], 
                        ascending=[False, True]
                    )
                    # Display the result matrix
                    st.dataframe(df_audit, width='stretch', hide_index=True)
                else:
                    st.warning("Could not find matching ticket columns between both sheets to subtract.")
            else:
                st.info("Waiting for both PrePack and Counted datasets to perform calculation.")



                #################################
             ######## Audit Chart ###########
                #################################
            st.write("Analytics View")
            # (...Keep original Page 2 Charts layout code intact...)
            chart2_data = df_audit.copy()
            if chart2_data.empty:
                st.warning("No data matches the selected timeframe bounds or global filter criteria.")
            else:
                # 1. Define all the ticket type columns we want to stack/color by
                ticket_columns = TICKET_COLUMNS
                
                available_tickets = [col for col in ticket_columns if col in chart2_data.columns]

                # CHANGED: barmode="group" places categories side-by-side
                fig = px.bar(
                    chart2_data, 
                    x="Bag Number", 
                    y=available_tickets,
                    title="Audit Results by Bag & Ticket Category",
                    barmode="group",  
                    height=600, 
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                
                # 1. Clean up layout axes (Removing vertical dotted grid lines)
                fig.update_layout(
                    hovermode="closest",  
                    plot_bgcolor="white",
                    xaxis={
                        'type': 'category',
                        'showgrid': False,     # Strips out the vertical grid lines entirely
                    }, 
                    yaxis={
                        'zeroline': True,      
                        'zerolinecolor': 'black',
                        'zerolinewidth': 1.5,
                        'showgrid': True,      # Keep horizontal lines for tracking values
                        'gridcolor': '#F0F0F0'
                    },
                    yaxis_title="Count / Discrepancy",
                    xaxis_title="Bag Number",
                    legend_title_text="Ticket Type"
                )

                # 2. Add alternating gray background shading for each unique bag group
                unique_bags = chart2_data["Bag Number"].unique().tolist()
                
                for index, bag in enumerate(unique_bags):
                    if index % 2 == 0:  # Alternate every other bag group
                        fig.add_vrect(
                            x0=index - 0.5,   # Stretch shading from the left edge of the group boundary
                            x1=index + 0.5,   # To the right edge of the group boundary
                            fillcolor="#F7F7F8", 
                            opacity=1.0, 
                            layer="below",    # Forces the shading background behind the colorful data bars
                            line_width=0
                        )
                        
                st.plotly_chart(fig, use_container_width=True)
            
    # ===================================================
    # NEW PAGE 4: LIVE WORKBAG SHEET ALLOCATION EDITOR (VIA ZAPIER)
    # =========================================================================
    elif page_selection == "📝 Count Stuff Out":
        st.subheader("📝 Live Shift & Bag Allocation Editor")
        
        if not is_authenticated:
            st.warning("🔒 Access Denied. Please authenticate via the sidebar panel.")
        elif df_excel_counted.empty:
            st.warning("Database registry is empty or inaccessible.")
        else:
            run_zapier(df_excel_counted.copy(), "Counted")

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
                final_edited_df = st.data_editor(df_reconciled_output, width='stretch', hide_index=True)
                
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
                    width='stretch'
                )



# st.markdown(
#     """
#     <style>
#         /* === 1. TEXT SIZE OVERRIDES === */
#         /* Make all radio option labels and checkbox labels bigger */
#         div[data-testid="stRadio"] label p, 
#         div[data-testid="stCheckbox"] label p,
#         div[data-testid="stCheckbox"] p {
#             font-size: 19px !important;
#             font-weight: 500 !important;
#             line-height: 1.2 !important;
#         }
        
#         /* Make widget headers bigger (e.g., "Go to view:", "Ticket Shortcuts:") */
#         div[data-testid="stRadio"] > label,
#         div[data-testid="stCheckboxGroup"] > label {
#             font-size: 21px !important;
#             font-weight: bold !important;
#             margin-bottom: 4px !important;
#         }

#         /* === 2. SPACING REDUCTION OVERRIDES === */
#         /* Reduce spacing between individual radio options */
#         div[data-testid="stRadio"] div[role="radiogroup"] > div {
#             padding-top: 2px !important;
#             padding-bottom: 2px !important;
#             margin-bottom: 0px !important;
#         }

#         /* Reduce spacing between individual checkboxes */
#         div[data-testid="stCheckbox"] {
#             margin-bottom: -4px !important;
#             padding-top: 0px !important;
#             padding-bottom: 0px !important;
#         }

#         /* Tighten up the container wrapping the widget elements */
#         div[data-testid="stRadio"] div[role="radiogroup"],
#         div[data-testid="stCheckboxGroup"] {
#             gap: 2px !important;
#         }
        
#         /* Scale up icons slightly to match text */
#         div[data-testid="stRadio"] input[type="radio"] + div {
#             transform: scale(1.15);
#         }
#         div[data-testid="stCheckbox"] input[type="checkbox"] + div {
#             transform: scale(1.15);
#         }
#     </style>
#     """,
#     unsafe_allow_html=True
# )

# st.sidebar.markdown(
#     """
#     <style>
#         /* 1. Make the radio button text larger */
#         div[data-testid="stRadio"] label p {
#             font-size: 20px !important;
#             font-weight: 500 !important;
#         }
        
#         /* 2. Scale up the actual radio outer circle icons */
#         div[data-testid="stRadio"]  div[role="radiogroup"] [data-testid="stWidgetLabel"] + div div[class*="st-"] {
#             transform: scale(1.5);
#             margin-right: 5px;
#         }

#         /* 3. Make the section header text larger (Go to view:) */
#         div[data-testid="stRadio"] > label {
#             font-size: 22px !important;
#             font-weight: bold !important;
#         }
#     </style>
#     """,
#     unsafe_allow_html=True
# )