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
            if name.lower() not in ['tech', 'team', 'the', 'is', 'hi', 'dear']:
                return name

    tech_keywords = ['tech', 'developer', 'dev ', 'development', 'backend', 'software']
    combined_text = (note + " " + category + " " + title).lower()
    if any(kw in combined_text for kw in tech_keywords):
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_data(file):
    df = pd.read_csv(file)
    
    # 1. Clean Headers
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # 2. Filter for 'Working' status only
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    
    if df.empty:
        return pd.DataFrame()

    # 3. Parse Created On Date (DD-MM-YYYY HH:MM)
    # dayfirst=True ensures DD-MM-YYYY is prioritized
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Created On'])

    # 4. Calculate Active Days (Simple Integer: Today - Created Date)
    current_time = datetime.now()
    # Subtract dates and extract the .days property to get a clean number
    df['Active Days'] = (current_time - df['Created On']).dt.days
    
    # 5. Severity & SLA Calculation
    # 1->4h, 2->8h, 3->48h, 4->4 days
    df['Severity'] = pd.to_numeric(df['Severity'], errors='coerce').fillna(4).astype(int)
    
    def calc_completion(row):
        start = row['Created On']
        sev = row['Severity']
        if sev == 1: return start + timedelta(hours=4)
        if sev == 2: return start + timedelta(hours=8)
        if sev == 3: return start + timedelta(hours=48)
        return start + timedelta(days=4)

    df['Expected Completion Date'] = df.apply(calc_completion, axis=1)
    
    # Format the completion date as M/D/YYYY HH:MM
    df['Expected Completion'] = df['Expected Completion Date'].dt.strftime('%-m/%-d/%Y %H:%M')
    
    # Map Severity to Priority Label
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)

    # 6. Extract Assigned To
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)

    # 7. Final Column Selection and Renaming
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
            st.warning("No tickets with 'Working' status found.")
        else:
            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Tickets", len(data))
            c2.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1', 'P2'])]))
            c3.metric("Oldest (Days)", int(data['Active Days'].max()))

            # Table Display
            st.subheader("Ticket Management Table")
            st.dataframe(
                data.sort_values(by='Active Days', ascending=False),
                use_container_width=True,
                hide_index=True
            )

            # Download CSV
            csv = data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", csv, "syrow_dashboard.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload the Caliper Report CSV to begin.")
