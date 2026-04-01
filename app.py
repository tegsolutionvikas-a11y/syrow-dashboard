import streamlit as st
import pandas as pd
import re
from datetime import timedelta

st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")
st.title("📊 Syrow Ticket Management Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV", type=["csv"])

def extract_assigned_person(row):
    # Convert to string and handle empty values
    note = str(row['Notes']).lower() if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    title = str(row['Ticket Title']).lower() if pd.notna(row['Ticket Title']) else ""
    
    # 1. Search for specific names following action words
    patterns = [
        r'assigned to\s+([A-Za-z]+)',
        r'escalated to\s+([A-Za-z]+)',
        r'allocated to\s+([A-Za-z]+)',
        r'moved to\s+([A-Za-z]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            return match.group(1).title()
    
    # 2. IMPROVED TECH TEAM LOGIC:
    # Check if "tech", "dev", or "developer" appears in Notes, Category, or Title
    tech_keywords = ['tech', 'developer', 'dev ', 'development', 'backend', 'software']
    if any(kw in note for kw in tech_keywords) or \
       any(kw in category for kw in tech_keywords) or \
       any(kw in title for kw in tech_keywords):
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_data(file):
    df = pd.read_csv(file)
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)
    
    # Apply the new smarter assignment logic
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    
    df['Created On'] = pd.to_datetime(df['Created On'])
    def get_sla(row):
        c, p = row['Created On'], row['Priority']
        hours = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
        return c + timedelta(hours=hours.get(p, 0))
    
    df['Expected Completion'] = df.apply(get_sla, axis=1)
    
    res = df[['Ticket SR#', 'KAM', 'Company', 'Priority', 'Ticket Title', 'Assigned To', 'Expected Completion']].copy()
    res.columns = ['Ticket No', 'KAM Name', 'Company Name', 'Priority', 'Issue Statement', 'Assigned To', 'Expected Completion']
    return res

if uploaded_file:
    data = process_data(uploaded_file)
    
    # KPIs
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Working Tickets", len(data))
    m2.metric("Tech Team Tickets", len(data[data['Assigned To'] == "Tech Team"]))
    m3.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1', 'P2'])]))
    
    # Table
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", data.to_csv(index=False), "dashboard.csv", "text/csv")
else:
    st.info("Please upload the CSV file to see the updated 'Tech Team' assignments.")
