import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Syrow Ticket Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    """Logic to identify the person handling the ticket."""
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    # Check for Deva
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"
    # Find names following 'to', 'assigned to', etc.
    match = re.search(r'(?:assigned to|escalated to|to)\s+([A-Z][a-z]+)', note)
    if match:
        name = match.group(1)
        if name.lower() not in ['tech', 'team', 'the', 'is', 'hi', 'dear']:
            return name
    return "-"

@st.cache_data
def process_data(file):
    # Load data and clean column names
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # 1. Filter for 'Working' status only
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    if df.empty: return pd.DataFrame()

    # 2. Strict Date Parsing (DD-MM-YYYY HH:MM)
    # Using dayfirst=True ensures DD-MM-YYYY is read correctly
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Created On'])
    if df.empty: return pd.DataFrame()

    # 3. Calculate ACTIVE DAYS (Hard Force to Integer)
    # We use (Now - Created) and then extract just the .days property
    now = pd.Timestamp.now()
    df['Active Days'] = (now - df['Created On']).dt.days.fillna(0).astype(int)
    
    # 4. Calculate EXPECTED COMPLETION (Strict TAT Rules)
    # 1 -> 4h | 2 -> 8h | 3 -> 48h | 4 -> 4 days
    df['Severity'] = pd.to_numeric(df['Severity'], errors='coerce').fillna(4).astype(int)
    
    def get_tat_date(row):
        start = row['Created On']
        sev = row['Severity']
        if sev == 1: delta = timedelta(hours=4)
        elif sev == 2: delta = timedelta(hours=8)
        elif sev == 3: delta = timedelta(hours=48)
        else: delta = timedelta(days=4)
        
        # KEY FIX: Convert to string immediately to stop the garbled numbers
        return (start + delta).strftime('%m/%d/%Y %H:%M')

    df['Expected Completion'] = df.apply(get_tat_date, axis=1)
    
    # 5. Final Formatting
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)

    # Prepare final columns
    result = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority', 
        'Ticket Title', 'Assigned To', 'Active Days', 'Expected Completion'
    ]].copy()

    result.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 'Priority', 
        'Issue Statement', 'Assigned To', 'Active Days', 'Expected Completion'
    ]
    
    return result

if uploaded_file:
    try:
        data = process_data(uploaded_file)
        
        if data.empty:
            st.warning("No 'Working' tickets found in this file.")
        else:
            # Dashboard Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Tickets", len(data))
            c2.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1', 'P2'])]))
            c3.metric("Oldest Ticket (Days)", int(data['Active Days'].max()))

            # The Table
            st.subheader("Live Ticket Queue")
            # We use .astype(str) on columns to ensure the table displays clean text
            st.dataframe(
                data.sort_values(by='Active Days', ascending=False),
                use_container_width=True,
                hide_index=True
            )

            # Download Option
            csv_out = data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download This Table", csv_out, "syrow_dashboard.csv", "text/csv")

    except Exception as e:
        st.error(f"Processing Error: {e}")
else:
    st.info("Please upload the 'Caliper Reports' CSV file.")
