import os
import json
import requests
import asyncio  # <-- Required to run the async loop
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import pandas as pd
import datetime
import streamlit as st
import tempfile

temp_dir = tempfile.gettempdir()

# Load variables from the local .env file
load_dotenv()

try:
    LOGIN_EMAIL = os.environ.get("EVENTENY_EMAIL")
    LOGIN_PASSWORD = os.environ.get("EVENTENY_PASSWORD")
    EVENT_ID = os.environ.get("EVENTENY_EVENT_ID_26")
except Exception:
    LOGIN_EMAIL = st.secrets.get("EVENTENY_EMAIL")
    LOGIN_PASSWORD = st.secrets.get("EVENTENY_PASSWORD")
    EVENT_ID = st.secrets.get("EVENTENY_EVENT_ID_26")

if not all([LOGIN_EMAIL, LOGIN_PASSWORD, EVENT_ID]):
    raise ValueError("Missing environment variables. Please check your .env file setup.")

# 1. Marked as async since it contains await expressions
async def get_authenticated_session():
    """Launches a brief headless browser to securely log in, bypass any 
    CSRF/bot defenses, and extract a live valid cookie jar.
    """
    print("Launching browser automation to sign in...")
    session = requests.Session()
    
    # 2. Used "async with" for the async context manager
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,executable_path="/usr/bin/chromium")
        context = await browser.new_context()
        page = await context.new_page()
        
        # Go to the actual login interface
        await page.goto('https://www.eventeny.com/users/?ref=/login/')

        # Fill out login credentials
        await page.fill('input[type="email"]', LOGIN_EMAIL)
        await page.fill('input[type="password"]', LOGIN_PASSWORD)
        await page.locator('button:has-text("Sign in"), input[type="submit"]').first.click()

        # Wait for login redirection to finish
        await page.click('text=Organize') 
        print("Login sequence successfully authenticated via browser!")
        
        # Extract the fresh, live cookies from the browser session
        # 3. cookies() must be awaited in the async API
        browser_cookies = await context.cookies()
        for cookie in browser_cookies:
            # Note: requests.Session().cookies.set is synchronous, no await needed here
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
            
        await browser.close()
        
    return session

# 4. Marked as async because it calls and awaits get_authenticated_session
async def automated_data_extraction():
    try:
        session = await get_authenticated_session()
    except Exception as e:
        print(f"Browser login phase failed: {str(e)}")
        return

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
        'accept': '*/*',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'referer': f'https://www.eventeny.com/dashboard/events/event/tickets/list/?id={EVENT_ID}',
        'origin': 'https://www.eventeny.com'
    }

    export_payload = [
        ('1', '1'),
        ('type', 'uploaded file'),
        ('export-type', 'attendee-ticket'),
        ('selections[export-type]', 'attendee-ticket'),
        ('selections[ticket]', '33312,33314,38046,38047,33315,38344,29623,36873,33309,33310,33311,33308,29591,36875,29592,33304,38503,36874,29593,36876,33302,33305,33319,33318,33303,33306,33316,33317,36878,36879,36880,33320,36884,36885,36882,33301,38346,29588,29587,30179,29589,33288,33307,36886,36883'),
        ('export-status', 'all'),
        ('selections[export-status]', 'all'),
        ('date-range', 'all'),
        ('selections[date-range]', 'all'),
        ('export[start_date]', 'Jan 1, 2026'),
        ('export[end_date]', 'Jun 21, 2026'),
        ('toggle_ticket_group', ''),
        ('export[merge_questions]', '1'),
        ('export[merge_deliverables]', '1'),
        
        # Base Columns
        ('export_columns[]', 'holder_first_name'),
        ('export_columns[]', 'holder_last_name'),
        ('export_columns[]', 'tags'),
        ('export_columns[]', 'first_name'),
        ('export_columns[]', 'last_name'),
        ('export_columns[]', 'payment_source'),
        ('export_columns[]', 'order_id'),
        ('export_columns[]', 'ticket_name'),
        ('export_columns[]', 'conf_code'),
        ('export_columns[]', 'status'),
        ('export_columns[]', 'timestamp'),
        ('export_columns[]', 'issued_by'),
        ('export_columns[]', 'issuer_full_name'),
        ('export_columns[]', 'seat_name'),
        ('export_columns[]', 'seat_section_name'),
        ('export_columns[]', 'time_slot_date'),
        ('export_columns[]', 'time_slot_open'),
        ('export_columns[]', 'time_slot_closed'),
        ('export_columns[]', 'cancel_time'),
        
        # Deliverables / Addons
        ('export_columns[]', 'deliverable-11002-3 Days Meals Ticket'),
        ('export_columns[]', 'deliverable-11005-All Access Parking Sticker'),
        ('export_columns[]', 'deliverable-11740-Friday Meal Ticket'),
        ('export_columns[]', 'deliverable-11741-Saturday Meal Ticket'),
        
        # Operations & Financial Metrics
        ('export_columns[]', 'checkin_time'),
        ('export_columns[]', 'checkin_by_fn'),
        ('export_columns[]', 'price'),
        ('export_columns[]', 'time_slot_upcharge'),
        ('export_columns[]', 'seat_upcharge'),
        ('export_columns[]', 'discount_title'),
        ('export_columns[]', 'discount_code'),
        ('export_columns[]', 'discount'),
        ('export_columns[]', 'affiliate_name'),
        ('export_columns[]', 'additional_fees'),
        ('export_columns[]', 'sales_tax'),
        ('export_columns[]', 'fees_passed'),
        ('export_columns[]', 'amount'),
        ('export_columns[]', 'fees_charged'),
        ('export_columns[]', 'payout'),
        ('export_columns[]', 'payout_excl_tax'),
        ('export_columns[]', 'payout_account_id'),
        ('export_columns[]', 'payout_account_name'),
        ('export_columns[]', 'refund_by_fn'),
        ('export_columns[]', 'refund_time'),
        ('export_columns[]', 'refund_amt'),
        ('export_columns[]', 'fees_refunded')
    ]

    print("Requesting master Excel export stream from primary document endpoint...")
    # Keeping requests synchronous as before
    response = session.post(
        f'https://www.eventeny.com/dashboard/events/event/tickets/list/?id={EVENT_ID}',
        headers=headers,
        data=export_payload
    )

    if response.status_code == 200:
        filename = f"live_tickets_raw_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        raw_csv_path = f"{filename}.csv"
        full_csv_path = os.path.join(temp_dir, raw_csv_path)
        
        with open(full_csv_path, "wb") as f:
            f.write(response.content)
        print("Downloaded master CSV successfully.")

        return full_csv_path
    else:
        print(f"Export failed with status code: {response.status_code}")
        return None
    
if __name__ == "__main__":
    # 5. Execute the async loop
    file_path = asyncio.run(automated_data_extraction())