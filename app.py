import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Syrow Ticket Management", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def parse_date_strictly(date_str):
    """Parses date manually to prevent month/day swap errors."""
    date_str = str(date_str).strip()
    # Try the two common formats found in your Syrow files
    for fmt in ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def extract_handler(note, category, title):
    """Finds the person assigned to the ticket."""
    text = f"{note} {category} {title}".lower()
    if "devagiri" in text or "deva" in text:
        return "Devagiri"
    
    # Look for name following 'to' or 'assigned to'
    match = re.search(r'(?:assigned to|escalated to|to)\s+([A-Z][a-z]+)', str(note))
    if match:
        name = match.group(1)
        if name.lower() not in ['tech', 'team', 'the', 'is', 'hi', 'dear']:
            return name
    return "-"

@st.cache_data
def process_data(file):
    # Load raw data
    raw_df = pd.read_csv(file)
    # Clean headers
    raw_df.columns = raw_df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # Filter for 'Working' status only
    raw_df = raw_df[raw_df['Status'].astype(str).str.strip().str.lower() == 'working']
    
    now = datetime.now()
    final_rows = []

    for _, row in raw_df.iterrows():
        # 1. Parse Date
        created_dt = parse_date_strictly(row['Created On'])
        if not created_dt:
            continue

        # 2. Extract Severity & Assign Defined TAT Delta
        try:
            sev = int(row['Severity'])
        except:
            sev = 4
            
        if sev == 1: 
            delta = timedelta(hours=4)
        elif sev == 2: 
            delta = timedelta(hours=8)
        elif sev == 3: 
            delta = timedelta(days=3)
        else: 
            delta = timedelta(days=4)
        
        # 3. Calculate Target Completion Date (Formatted as DD/MM/YY HH:MM)
        expected_dt = created_dt + delta
        expected_str = expected_dt.strftime('%d/%m/%y %H:%M')

        # 4. Universal Countdown / Aging Logic
        remaining_seconds = (expected_dt - now).total_seconds()
        days_remaining = int(remaining_seconds // 86400)

        # 5. Map Priority Header
        priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
        
        # 6. Build clean row record
        final_rows.append({
            'Ticket No': str(row['Ticket SR#']),
            'KAM Name': str(row['KAM']),
            'Company Name': str(row['Company']),
            'Priority': priority_map.get(sev, 'P4'),
            'Issue Statement': str(row['Ticket Title']),
            'Assigned To': extract_handler(row.get('Notes', ''), row.get('Ticket Category', ''), row.get('Ticket Title', '')),
            'Days Remaining': str(days_remaining),
            'Expected Completion': expected_str
        })

    return pd.DataFrame(final_rows)

if uploaded_file:
    try:
        data = process_data(uploaded_file)
        
        if data.empty:
            st.warning("No tickets with status 'Working' found.")
        else:
            # Key Performance Indicators
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Tickets", len(data))
            c2.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1', 'P2'])]))
            
            # Count overdue tickets across all priorities (Days Remaining < 0)
            overdue_count = sum(1 for x in data['Days Remaining'] if int(x) < 0)
            c3.metric("Overdue Tickets", overdue_count)

            # Display the main Queue
            st.subheader("Live Ticket Queue")
            
            # Sort ascending so negative/overdue tickets stay at top
            data['sort_col'] = data['Days Remaining'].astype(int)
            display_df = data.sort_values('sort_col', ascending=True).drop(columns=['sort_col'])
            
            # Static table prevents UI formatting glitches
            st.table(display_df)

            # Clean CSV export
            csv_data = display_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", csv_data, "syrow_report.csv", "text/csv")

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Please upload the Caliper Report CSV to begin.")
