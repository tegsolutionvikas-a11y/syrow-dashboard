import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Syrow Ticket Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"
    
    match = re.search(r'(?:assigned to|escalated to|to)\s+([A-Z][a-z]+)', note)
    if match:
        name = match.group(1)
        if name.lower() not in ['tech', 'team', 'the', 'is', 'hi', 'dear']:
            return name
    return "-"

@st.cache_data
def process_data(file):
    df = pd.read_csv(file)
    
    # 1. Clean Headers
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # 2. Filter for 'Working' status
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    if df.empty: return pd.DataFrame()

    # 3. ROBUST DATE PARSING (Forcing Day First for DD-MM-YYYY)
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Created On'])
    if df.empty: return pd.DataFrame()

    # --- THE HARD FIX FOR ACTIVE DAYS ---
    now = datetime.now()
    # We calculate total seconds and divide by 86400 to get a clean WHOLE number
    df['Active Days'] = df['Created On'].apply(lambda x: int((now - x).total_seconds() // 86400))
    
    # --- THE HARD FIX FOR EXPECTED COMPLETION ---
    df['Severity'] = pd.to_numeric(df['Severity'], errors='coerce').fillna(4).astype(int)
    
    def calculate_tat(row):
        start = row['Created On']
        sev = row['Severity']
        if sev == 1: delta = timedelta(hours=4)
        elif sev == 2: delta = timedelta(hours=8)
        elif sev == 3: delta = timedelta(hours=48)
        else: delta = timedelta(days=4)
        
        # We return a formatted STRING immediately to prevent the object bug
        return (start + delta).strftime('%m/%d/%Y %H:%M')

    df['Expected Completion'] = df.apply(calculate_tat, axis=1)
    
    # 4. Final Preparation
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)

    # Filter and Rename
    result = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority', 
        'Ticket Title', 'Assigned To', 'Active Days', 'Expected Completion'
    ]].copy()

    result.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 'Priority', 
        'Issue Statement', 'Assigned To', 'Active Days', 'Expected Completion'
    ]
    
    # Force Active Days to be an integer type one last time
    result['Active Days'] = result['Active Days'].astype(int)
    
    return result

if uploaded_file:
    try:
        data = process_data(uploaded_file)
        
        if data.empty:
            st.warning("No 'Working' tickets found.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Active Tickets", len(data))
            m2.metric("P1/P2 Critical", len(data[data['Priority'].isin(['P1', 'P2'])]))
            m3.metric("Oldest (Days)", int(data['Active Days'].max()))

            st.subheader("Live Ticket Queue")
            # We use .astype(str) on the whole dataframe display to stop Streamlit's auto-formatting
            st.dataframe(
                data.sort_values(by='Active Days', ascending=False),
                use_container_width=True,
                hide_index=True
            )

            csv_data = data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", csv_data, "dashboard.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload the Caliper Report CSV.")
