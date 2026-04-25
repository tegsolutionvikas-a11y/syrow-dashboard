import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    """
    Scans Notes, Category, and Title to identify the person or team 
    currently handling the ticket using Regex.
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
            if name.lower() not in ['tech', 'still', 'currently', 'team']:
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
    
    # Filter for Working status and create a fresh copy to avoid SettingWithCopy warnings
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    # Priority Mapping
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)
    
    # Apply smarter assignment logic
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    
    # Convert 'Created On' to datetime objects
    df['Created On'] = pd.to_datetime(df['Created On'], errors='coerce')
    
    # Drop rows where date conversion failed to prevent calculation errors
    df = df.dropna(subset=['Created On'])
    
    today = datetime.now()
    
    # Calculate how many days the ticket has been active
    df['Active Days'] = (today - df['Created On']).dt.days
    
    # --- FIXED SLA CALCULATION ---
    # We use mapping and vectorized addition instead of row-wise apply
    hours_map = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
    
    # Map priorities to hour values (default to 0 if not found)
    sla_hours = df['Priority'].map(hours_map).fillna(0)
    
    # Add the timedelta to the creation date
    df['Expected Completion'] = df['Created On'] + pd.to_timedelta(sla_hours, unit='h')
    # -----------------------------
    
    # Final Table selection (Ordering and Renaming)
    res = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority', 
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
        
        # KPIs for quick overview
        m1, m2, m3 = st.columns(3)
        m1.metric("Active Working Tickets", len(data))
        
        # Tech load calculation
        tech_load = len(data[data['Assigned To'].isin(["Tech Team", "Devagiri"])])
        m2.metric("Tech Team / Dev Load", tech_load)
        
        # Critical priority calculation
        critical_count = len(data[data['Priority'].isin(['P1', 'P2'])])
        m3.metric("Critical (P1/P2)", critical_count)
        
        # Table display
        st.subheader("Live Ticket Queue")
        st.dataframe(data, use_container_width=True, hide_index=True)
        
        # Export capability
        csv_data = data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Dashboard CSV", 
            data=csv_data, 
            file_name="syrow_active_tickets.csv", 
            mime="text/csv"
        )
        
    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
        st.info("Check if your CSV has the required columns: Ticket SR#, KAM, Company, Severity, Status, Created On, Notes, Ticket Category, Ticket Title")

else:
    st.info("Please upload the Syrow CSV file to view the standardized dashboard.")
