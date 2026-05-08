import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Syrow Dashboard", layout="wide")
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
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # 1. Filter for 'Working'
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    if df.empty: return pd.DataFrame()

    # 2. Strict Date Parsing
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Created On'])
    
    # 3. MANUAL CALCULATION (Avoids the Timedelta object bug)
    now = datetime.now()
    active_days_list = []
    expected_comp_list = []
    
    for _, row in df.iterrows():
        # Calculate Active Days as a pure integer
        diff = now - row['Created On']
        active_days_list.append(int(diff.total_seconds() // 86400))
        
        # Calculate SLA based on your rules
        sev = 4
        try:
            sev = int(row['Severity'])
        except:
            pass
            
        if sev == 1: delta = timedelta(hours=4)
        elif sev == 2: delta = timedelta(hours=8)
        elif sev == 3: delta = timedelta(hours=48)
        else: delta = timedelta(days=4)
        
        # Force completion date to a plain text string immediately
        target = row['Created On'] + delta
        expected_comp_list.append(target.strftime('%m/%d/%Y %H:%M'))

    # Assign clean lists back to dataframe
    df['Active Days'] = active_days_list
    df['Expected Completion'] = expected_comp_list
    
    # 4. Final Formatting
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = pd.to_numeric(df['Severity'], errors='coerce').fillna(4).astype(int).map(priority_map)

    result = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority', 
        'Ticket Title', 'Assigned To', 'Active Days', 'Expected Completion'
    ]].copy()

    result.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 'Priority', 
        'Issue Statement', 'Assigned To', 'Active Days', 'Expected Completion'
    ]
    
    # FINAL LOCK: Force the entire column to be seen as strings/ints
    result['Active Days'] = result['Active Days'].astype(int)
    result['Ticket No'] = result['Ticket No'].astype(str)
    
    return result

if uploaded_file:
    try:
        data = process_data(uploaded_file)
        if data.empty:
            st.warning("No 'Working' tickets found.")
        else:
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Active Tickets", len(data))
            m2.metric("P1/P2 Critical", len(data[data['Priority'].isin(['P1', 'P2'])]))
            m3.metric("Oldest (Days)", int(data['Active Days'].max()))

            # Table display - Sorted by Active Days
            st.subheader("Live Ticket Queue")
            st.table(data.sort_values(by='Active Days', ascending=False))

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload the Caliper Report CSV.")
