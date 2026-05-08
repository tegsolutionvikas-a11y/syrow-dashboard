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

        # 2. Calculate Active Days (Force to a simple whole number)
        seconds_diff = (now - created_dt).total_seconds()
        active_days = int(seconds_diff // 86400)

        # 3. Calculate Severity & Expected Completion
        try:
            sev = int(row['Severity'])
        except:
            sev = 4
            
        if sev == 1: delta = timedelta(hours=4)
        elif sev == 2: delta = timedelta(hours=8)
        elif sev == 3: delta = timedelta(hours=48)
        else: delta = timedelta(days=4)
        
        expected_dt = created_dt + delta
        # Format as simple text string immediately
        expected_str = expected_dt.strftime('%m/%d/%Y %H:%M')

        # 4. Map Priority
        priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
        
        # 5. Build clean dictionary (All values are simple strings or ints)
        final_rows.append({
            'Ticket No': str(row['Ticket SR#']),
            'KAM Name': str(row['KAM']),
            'Company Name': str(row['Company']),
            'Priority': priority_map.get(sev, 'P4'),
            'Issue Statement': str(row['Ticket Title']),
            'Assigned To': extract_handler(row.get('Notes', ''), row.get('Ticket Category', ''), row.get('Ticket Title', '')),
            'Active Days': str(active_days), # Forced to string to stop the '3232' bug
            'Expected Completion': expected_str
        })

    return pd.DataFrame(final_rows)

if uploaded_file:
    try:
        data = process_data(uploaded_file)
        
        if data.empty:
            st.warning("No tickets with status 'Working' found.")
        else:
            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Tickets", len(data))
            c2.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1', 'P2'])]))
            
            # Use the plain string for the metric to avoid errors
            oldest = max([int(x) for x in data['Active Days']])
            c3.metric("Oldest (Days)", oldest)

            # Display the table
            st.subheader("Live Ticket Queue")
            
            # Sort by Active Days (converting back to int just for the sort)
            data['sort_col'] = data['Active Days'].astype(int)
            display_df = data.sort_values('sort_col', ascending=False).drop(columns=['sort_col'])
            
            # Use st.table (static) instead of st.dataframe (interactive) 
            # because st.dataframe is what is causing the formatting bug.
            st.table(display_df)

            # Download CSV
            csv = data.drop(columns=['sort_col'] if 'sort_col' in data else []).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", csv, "syrow_report.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload the Caliper Report CSV to begin.")
