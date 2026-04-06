import streamlit as st
import pandas as pd
import re
from datetime import timedelta

st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    title = str(row['Ticket Title']).lower() if pd.notna(row['Ticket Title']) else ""
    
    # 1. Check for specific variants of Devagiri / Deva
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"

    # 2. Search for "Assigned to / Escalated to [Name]"
    action_patterns = [
        r'(?:assigned to|escalated to|allocated to|moved to|forwarded to)\s+([A-Za-z]+)',
        r'([A-Za-z]+)\s+is\s+working\s+on\s+this',  # Matches "Deva is working on this"
        r'([A-Za-z]+)\s+working'                   # Matches "Somnath working"
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            name = match.group(1).title()
            # Clean up common non-name words that might get caught by the "working" regex
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
    df = pd.read_csv(file)
    # Filter for Working status
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    # Priority Mapping
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)
    
    # Apply smarter assignment logic
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    
    # SLA Calculation
    df['Created On'] = pd.to_datetime(df['Created On'])
    def get_sla(row):
        c, p = row['Created On'], row['Priority']
        hours = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
        return c + timedelta(hours=hours.get(p, 0))
    
    df['Expected Completion'] = df.apply(get_sla, axis=1)
    
    # Final Table selection
    res = df[['Ticket SR#', 'KAM', 'Company', 'Priority', 'Ticket Title', 'Assigned To', 'Expected Completion']].copy()
    res.columns = ['Ticket No', 'KAM Name', 'Company Name', 'Priority', 'Issue Statement', 'Assigned To', 'Expected Completion']
    return res

if uploaded_file:
    data = process_data(uploaded_file)
    
    # KPIs
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Working Tickets", len(data))
    m2.metric("Tech Team / Dev Load", len(data[data['Assigned To'].isin(["Tech Team", "Devagiri"])]))
    m3.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1', 'P2'])]))
    
    # Table display
    st.dataframe(data, use_container_width=True, hide_index=True)
    
    # Download Button
    st.download_button("📥 Download Dashboard CSV", data.to_csv(index=False), "syrow_dashboard.csv", "text/csv")
else:
    st.info("Please upload the Syrow CSV file to view the standardized dashboard.")
