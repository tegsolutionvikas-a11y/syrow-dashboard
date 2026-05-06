import streamlit as st
import pandas as pd
import re
from datetime import datetime

# Set page configuration
st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    """
    Scans Notes, Ticket Category, and Ticket Title to identify the person or team 
    handling the ticket using Regex.
    """
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    title = str(row['Ticket Title']).lower() if pd.notna(row['Ticket Title']) else ""
    
    # 1. Check for specific variants of Devagiri / Deva
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"

    # 2. Search for "Assigned to / Escalated to [Name]"
    action_patterns = [
        r'(?:assigned to|escalated to|allocated to|moved to|forwarded to)\s+([A-Za-z]+)',
        r'([A-Za-z]+)\s+is\s+working\s+on\s+this',
        r'([A-Za-z]+)\s+working'
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            name = match.group(1).title()
            # Filter out common false positives
            if name.lower() not in ['tech', 'still', 'currently', 'team', 'the', 'is']:
                return name

    # 3. Tech Team Fallback
    tech_keywords = ['tech', 'developer', 'dev ', 'development', 'backend', 'software']
    combined_text = (note + " " + category + " " + title).lower()
    if any(kw in combined_text for kw in tech_keywords):
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_data(file):
    # Load data
    df = pd.read_csv(file)
    
    # Filter for active tickets (Status: Working)
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    # Priority Mapping based on Severity column
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority_Label'] = df['Severity'].map(priority_map)
    
    # Apply assignment logic
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    
    # --- FIXED DATE CONVERSION ---
    # dayfirst=True ensures DD-MM-YYYY is read correctly, preventing the 30-day error
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    
    # Drop invalid dates to prevent calculation crashes
    df = df.dropna(subset=['Created On'])
    
    # Use current time for aging calculation
    today = datetime.now()
    
    # Calculate Active Days
    df['Active Days'] = (today - df['Created On']).dt.days
    
    # SLA CALCULATION
    hours_map = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
    sla_hours = df['Priority_Label'].map(hours_map).fillna(0)
    df['Expected Completion'] = df['Created On'] + pd.to_timedelta(sla_hours, unit='h')
    
    # Selecting and Renaming Columns for Display
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
        
        # Dashboard KPIs
        m1, m2, m3 = st.columns(3)
        m1.metric("Active Working Tickets", len(data))
        
        # Load for specific technical resources
        tech_load = len(data[data['Assigned To'].isin(["Tech Team", "Devagiri"])])
        m2.metric("Tech Team / Dev Load", tech_load)
        
        # Count of high-priority tickets
        critical_count = len(data[data['Priority'].isin(['P1', 'P2'])])
        m3.metric("Critical (P1/P2)", critical_count)
        
        # Data Table Display
        st.subheader("Live Ticket Queue (Status: Working)")
        st.dataframe(
            data.sort_values(by='Active Days', ascending=False), 
            use_container_width=True, 
            hide_index=True
        )
        
        # Download Link
        csv_data = data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Dashboard CSV", 
            data=csv_data, 
            file_name=f"syrow_dashboard_{datetime.now().strftime('%Y%m%d')}.csv", 
            mime="text/csv"
        )
        
    except Exception as e:
        st.error(f"Processing Error: {e}")
        st.info("Ensure the CSV contains these exact headers: Ticket SR#, KAM, Company, Severity, Status, Created On, Notes, Ticket Title")
else:
    st.info("Please upload the 'Caliper Reports' CSV file to begin.")
