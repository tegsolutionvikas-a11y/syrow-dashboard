import streamlit as st
import pandas as pd
import re
from datetime import datetime

# Set page configuration
st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    """Identifies the owner using keywords in Notes, Category, and Title."""
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    title = str(row['Ticket Title']).lower() if pd.notna(row['Ticket Title']) else ""
    
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"

    action_patterns = [
        r'(?:assigned to|escalated to|allocated to|moved to|forwarded to)\s+([A-Za-z]+)',
        r'([A-Za-z]+)\s+is\s+working\s+on\s+this',
        r'([A-Za-z]+)\s+working'
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            name = match.group(1).title()
            if name.lower() not in ['tech', 'still', 'currently', 'team', 'the', 'is']:
                return name

    tech_keywords = ['tech', 'developer', 'dev ', 'development', 'backend', 'software']
    combined_text = (note + " " + category + " " + title).lower()
    if any(kw in combined_text for kw in tech_keywords):
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_data(file):
    # Load data
    df = pd.read_csv(file)
    
    # Clean Column Names (removes hidden spaces or quotes)
    df.columns = df.columns.str.strip().str.replace('"', '').replace("'", "")
    
    # --- ROBUST FILTERING ---
    # Filter for 'working' (Case-insensitive & strip whitespace)
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    
    if df.empty:
        return pd.DataFrame()

    # Priority Mapping
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    # Ensure Severity is numeric for mapping
    df['Severity'] = pd.to_numeric(df['Severity'], errors='coerce')
    df['Priority_Label'] = df['Severity'].map(priority_map).fillna('P4')
    
    # Assignment Logic
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    
    # --- FLEXIBLE DATE CONVERSION ---
    # We remove 'format=' to let Pandas automatically detect if it's YYYY-MM-DD or DD-MM-YYYY
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    
    # Clean up any rows where the date failed to parse
    df = df.dropna(subset=['Created On'])
    
    if df.empty:
        return pd.DataFrame()
    
    # --- ACTIVE DAYS CALCULATION (Calendar Days) ---
    today = pd.Timestamp.now().normalize()
    df['Active Days'] = (today - df['Created On'].dt.normalize()).dt.days
    df['Active Days'] = df['Active Days'].clip(lower=0) # No negative days
    
    # SLA Calculation
    hours_map = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
    sla_hours = df['Priority_Label'].map(hours_map).fillna(0)
    df['Expected Completion'] = df['Created On'] + pd.to_timedelta(sla_hours, unit='h')
    
    # Selection & Rename
    res = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority_Label', 
        'Ticket Title', 'Assigned To', 'Active Days', 'Expected Completion'
    ]].copy()
    
    res.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 'Priority', 
        'Issue Statement', 'Assigned To', 'Active Days', 'Expected Completion'
    ]
    
    return res

if uploaded_file:
    try:
        data = process_data(uploaded_file)
        
        if data.empty:
            st.warning("No tickets with status 'Working' were found. Check your CSV filters.")
        else:
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Active Working Tickets", len(data))
            
            tech_load = len(data[data['Assigned To'].isin(["Tech Team", "Devagiri"])])
            m2.metric("Tech Team / Dev Load", tech_load)
            
            critical_count = len(data[data['Priority'].isin(['P1', 'P2'])])
            m3.metric("Critical (P1/P2)", critical_count)
            
            # Queue Table
            st.subheader("Live Ticket Queue (Status: Working)")
            st.dataframe(
                data.sort_values(by='Active Days', ascending=False), 
                use_container_width=True, 
                hide_index=True
            )
            
            # Download
            csv_data = data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Dashboard CSV", 
                data=csv_data, 
                file_name=f"syrow_dashboard_{datetime.now().strftime('%Y%m%d')}.csv", 
                mime="text/csv"
            )
        
    except Exception as e:
        st.error(f"Dashboard Error: {e}")
else:
    st.info("Please upload the 'Caliper Reports' CSV file to begin.")
