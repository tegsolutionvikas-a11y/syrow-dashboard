import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Syrow Ticket Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    """Identifies the handler from Notes, Category, or Title."""
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    title = str(row['Ticket Title']).lower() if pd.notna(row['Ticket Title']) else ""
    
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"

    action_patterns = [
        r'(?:assigned to|escalated to|forwarded to|to)\s+([A-Z][a-z]+)',
        r'([A-Z][a-z]+)\s+is\s+working',
        r'([A-Z][a-z]+)\s+working'
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, note)
        if match:
            name = match.group(1)
            if name.lower() not in ['tech', 'team', 'the', 'is', 'hi', 'dear', 'currently', 'still']:
                return name
    
    return "-"

@st.cache_data
def process_data(file):
    df = pd.read_csv(file)
    
    # Clean Headers
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # Filter for 'Working' status
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    
    if df.empty:
        return pd.DataFrame()

    # --- THE FIX: ROBUST DATE PARSING ---
    # We use dayfirst=True and a specific format to ensure DD-MM-YYYY is handled correctly
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Created On'])
    
    if df.empty:
        return pd.DataFrame()

    # --- CALCULATION LOGIC ---
    now = pd.Timestamp.now()

    # 1. Active Days (Force as a simple integer)
    # subtracting two timestamps gives a timedelta; .days extracts only the whole number
    df['Active Days'] = (now - df['Created On']).dt.days
    
    # 2. Expected Completion (SLA/TAT)
    # Rules: 1=4h, 2=8h, 3=48h, 4=4 days (96h)
    df['Severity'] = pd.to_numeric(df['Severity'], errors='coerce').fillna(4).astype(int)
    
    def calculate_tat(row):
        start = row['Created On']
        sev = row['Severity']
        if sev == 1: return start + timedelta(hours=4)
        if sev == 2: return start + timedelta(hours=8)
        if sev == 3: return start + timedelta(hours=48)
        return start + timedelta(days=4)

    df['Expected_DT'] = df.apply(calculate_tat, axis=1)
    
    # Format the completion date as a simple string to avoid display errors
    df['Expected Completion'] = df['Expected_DT'].dt.strftime('%-m/%-d/%Y %H:%M')
    
    # 3. Final Prep
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)

    # Reordering and renaming for the final Dashboard output
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
            st.warning("No 'Working' tickets found.")
        else:
            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Tickets", len(data))
            c2.metric("P1/P2 Critical", len(data[data['Priority'].isin(['P1', 'P2'])]))
            c3.metric("Oldest (Days)", int(data['Active Days'].max()))

            # Table
            st.subheader("Ticket Queue Table")
            st.dataframe(
                data.sort_values(by='Active Days', ascending=False),
                use_container_width=True,
                hide_index=True
            )

            # Download
            csv_data = data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", csv_data, "dashboard.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload the Caliper Report CSV.")
