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

GOOGLE_SHEET_CSV_URL = os.environ.get("GOOGLE_SHEET_EXPORT_URL")
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
    ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart", "🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations"]
)
st.sidebar.markdown("---")

# =========================================================================
# 🔒 PASSWORD PROTECTION GATE (Applies to both Page 3 and Page 4)
# =========================================================================
is_authenticated = True
if page_selection in ["🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations"]:
    st.sidebar.subheader("🔒 Authentication Required")
    user_password = st.sidebar.text_input("Enter Inventory Access Password:", type="password")
    if user_password == APP_PASSWORD:
        st.sidebar.success("Access Granted!")
        is_authenticated = True
    else:
        if user_password != "": st.sidebar.error("Incorrect Password")
        is_authenticated = False

# Fetch fresh copy from the cloud if authenticated
if is_authenticated and page_selection in ["🎒 Per-Bag Inventory Audit", "📝 Edit Shift Allocations"]:
    df_excel_registry = load_google_sheet_inventory(GOOGLE_SHEET_CSV_URL)
else:
    df_excel_registry = pd.DataFrame()

# =========================================================================
# MAIN DASHBOARD LOGIC
# =========================================================================
if df_raw.empty:
    st.info("Waiting for 'live_tickets.json' to populate...")
else:
    df_raw["Check-in by"] = df_raw["Check-in by"].fillna("Not Checked In")
    df_raw["Broad Category Group"] = df_raw["Ticket name"].apply(categorized_label)

    # Global variables required across analytical screens
    start_filter, end_filter = datetime.datetime.now(), datetime.datetime.now()
    filter_mode = "Broad Category Groups (Clean Summary)"
    selected_items, selected_agents = [], []

    # Render filters only on diagnostic analytics pages
    if page_selection in ["📋 Live Transaction Ledger", "📊 Check-In Analytics Chart", "🎒 Per-Bag Inventory Audit"]:
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
                        if st.checkbox(cat, value=(t_action == "Select All"), key=f"c_{i}"): selected_items.append(cat)
                else:
                    all_tickets = sorted(df_raw["Ticket name"].dropna().unique().tolist())
                    for i, ticket in enumerate(all_tickets):
                        if st.checkbox(ticket, value=(t_action == "Select All"), key=f"t_{i}"): selected_items.append(ticket)
                st.markdown('</div>', unsafe_allow_html=True)
            with f_col2:
                st.markdown("#### Check-in Agents / Staff")
                all_agents = sorted(df_raw["Check-in by"].unique().tolist())
                a_action = st.radio("Agent Shortcuts:", ["Select All", "Deselect All"], horizontal=True)
                st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
                for j, agent in enumerate(all_agents):
                    if st.checkbox(agent, value=(a_action == "Select All"), key=f"a_{j}"): selected_agents.append(agent)
                st.markdown('</div>', unsafe_allow_html=True)
            with f_col3:
                st.markdown("#### Global Datetime Bounds")
                valid_times = df_raw["Check-in time_parsed"].dropna()
                min_time = valid_times.min().replace(second=0, microsecond=0).to_pydatetime() if not valid_times.empty else pd.to_datetime("2026-01-01 00:00:00").to_pydatetime()
                max_time = valid_times.max().replace(second=0, microsecond=0).to_pydatetime() if not valid_times.empty else pd.to_datetime("2026-12-31 23:59:00").to_pydatetime()
                if min_time == max_time: max_time += datetime.timedelta(minutes=1)
                start_filter, end_filter = st.slider("Operational window:", min_value=min_time, max_value=max_time, value=(min_time, max_time), format="MM/DD HH:mm")

        ticket_mask = df_raw["Broad Category Group"].isin(selected_items) if filter_mode == "Broad Category Groups (Clean Summary)" else df_raw["Ticket name"].isin(selected_items)
        filtered_df = df_raw[ticket_mask & (df_raw["Check-in by"].isin(selected_agents)) & (df_raw["Check-in time_parsed"] >= start_filter) & (df_raw["Check-in time_parsed"] <= end_filter)].copy()

        total_rows = len(filtered_df)
        checked_in_count = (filtered_df["Status"] == "Checked In").sum()
        st.markdown("### Operational KPIs")
        m1, m2, m3 = st.columns(3)
        m1.metric("Records Filtered", f"{total_rows:,}")
        m2.metric("Total Checked In", f"{checked_in_count:,}")
        m3.metric("Check-In Progress", f"{(checked_in_count / total_rows * 100) if total_rows > 0 else 0:.1f}%")
        st.markdown("---")

    # =========================================================================
    # RENDER SELECTED PAGE SWITCH BLOCKS
    # =========================================================================
    if page_selection == "📋 Live Transaction Ledger":
        st.subheader("Live Operational Records View")
        # (...Keep original Page 1 Ledger layout code intact...)
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    elif page_selection == "📊 Check-In Analytics Chart":
        st.subheader("Check-In Velocity Timeline")
        # (...Keep original Page 2 Charts layout code intact...)
        st.write("Analytics View")

    elif page_selection == "🎒 Per-Bag Inventory Audit":
        st.subheader("Global Filter-Bound Performance Reconciliation Ledger")
        if not is_authenticated:
            st.warning("🔒 Access Denied. Input the correct password in the sidebar.")
        elif df_excel_registry.empty:
            st.warning("Could not fetch data from Google Sheet link.")
        else:
            # (...Keep your original Page 3 processing loop exact math code intact...)
            st.dataframe(df_excel_registry, use_container_width=True, hide_index=True)

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
            counter_name = st.text_input("Counter:", value=str("Please fill in"))

            # Fetch target row data
            row_data = df_excel_registry[df_excel_registry[bag_label] == selected_bag_to_edit].iloc[0]
            
            st.markdown("---")
            st.markdown(f"#### 🛠️ Step 2: Update Data Fields")
            
            with st.form("zapier_modifier_form"):
                c_meta1, c_meta2 = st.columns(2)
                with c_meta1:
                #     updated_gate = st.text_input("Gate Location:", value=str(row_data.get("Gate", "N/A")))
                     updated_name = st.text_input("Assigned Staff Member:", value=str(row_data.get("Name", "Please fill in")))
                with c_meta2:
                #     updated_start = st.text_input("Shift Start (HH:MM):", value=str(row_data.get("Shift Start", "00:00")))
                #     updated_end = st.text_input("Shift End (HH:MM):", value=str(row_data.get("Shift End", "23:59")))
                #with c_meta3:
                #     updated_day = st.text_input("Day Code Assignment:", value=str(row_data.get("Day", "saturday")))
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
                    "name": updated_name,
                    "counter": counter_name,
                    "notes": notes,
                }
                # Merge dynamic numbers directly into payload root
                for ticket_name, qty in ticket_inputs.items():
                    payload[f"ticket_{ticket_name}"] = qty

                with st.spinner("Firing webhook to Zapier..."):
                    try:
                        print(payload)
                        ZAPIER_HOOK_URL = "https://hooks.zapier.com/hooks/catch/28076615/42ath8o/"
                        response = requests.post(ZAPIER_HOOK_URL, json=payload)
                        
                        if response.status_code in [200, 201]:
                            st.success("🎉 Sent to Zapier! Now go to your Zapier dashboard to test the trigger.")
                        else:
                            st.error(f"Zapier rejected request with status code: {response.status_code}")
                    except Exception as e:
                        st.error(f"Failed to connect to Zapier webhook: {e}")