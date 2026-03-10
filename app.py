import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os

# 🔑 Gemini Setup
API_KEY = "YOUR_GEMINI_API_KEY"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})

HISTORY_FILE = "mapping_history.json"

# ==========================================
# 1. HELPER FUNCTIONS (History & Gemini)
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_history(history_data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history_data, f, indent=4)

def get_gemini_intelligence(entity, field, aggregated_data):
    """Sends aggregated dictionary to Gemini to get mapping and graph type"""
    prompt = f"""
    You are a Data Viz Expert. I am analyzing CRM data for the entity '{entity}' and field '{field}'.
    Here are the raw unique values and their counts: {json.dumps(aggregated_data)}
    
    1. Group these raw text values into logical, standardized categories (e.g., standardize '10-50' and '10 to 50' into one category).
    2. Suggest the best graph type for this data. Choose ONLY from: 'Bar Chart', 'Pie Chart', or 'Donut Chart'.
    
    Return STRICTLY JSON format:
    {{
        "graph_type": "Bar Chart",
        "mapping": {{
            "raw_value_1": "Standardized Category A",
            "raw_value_2": "Standardized Category A",
            "raw_value_3": "Standardized Category B"
        }}
    }}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gemini API Error: {e}")
        return None

# ==========================================
# 2. MOCK KYLAS DATA LOADER
# ==========================================
# Real use case mein yahan Kylas API / CSV loading aayegi
def load_mock_data(entity):
    if entity == "Companies":
        return pd.DataFrame({
            "Company Name": ["A", "B", "C", "D", "E"],
            "Employee Size": ["10-50", "50-200", "10 to 50", "200+", "1-10"],
            "Funding Type": ["Seed", "Series A", "Bootstrapped", "Seed", "Series B"]
        })
    elif entity == "Deals":
        return pd.DataFrame({
            "Deal Name": ["D1", "D2", "D3"],
            "Revenue Bracket": ["$10k-$50k", "$50k+", "$10k to $50k"]
        })
    return pd.DataFrame()

# ==========================================
# 3. STREAMLIT UI & LOGIC
# ==========================================
st.set_page_config(page_title="CRM Intelligence Dashboard", layout="wide")
st.title("📊 Kylas CRM Intelligence Dashboard")

# Load History
history = load_history()

# Sidebar Setup
st.sidebar.header("Data Selection")
entities = ["Leads", "Contacts", "Companies", "Deals"]
selected_entity = st.sidebar.selectbox("1. Select Module", entities)

# Load Data based on selection
df = load_mock_data(selected_entity)

if not df.empty:
    # Let user select the field
    columns = [col for col in df.columns if col not in ["Company Name", "Deal Name", "Contact Name", "ID"]]
    selected_field = st.sidebar.selectbox("2. Select Field to Analyze", columns)
    
    if st.sidebar.button("Analyze Data"):
        history_key = f"{selected_entity}_{selected_field}"
        
        # --- PANDAS AGGREGATION ---
        # Instead of feeding raw rows, we just get unique counts
        raw_counts = df[selected_field].value_counts().to_dict()
        
        intelligence = {}
        
        # --- CHECK HISTORY FIRST ---
        if history_key in history:
            st.success(f"⚡ Loaded mapping logic from History (Hardcoded state ready for {history_key})")
            intelligence = history[history_key]
        else:
            # --- CALL GEMINI ONLY IF NEW ---
            with st.spinner('🧠 Calling Gemini AI to map categories and suggest graph...'):
                intelligence = get_gemini_intelligence(selected_entity, selected_field, raw_counts)
                
                if intelligence:
                    # Save to history for future use
                    history[history_key] = intelligence
                    save_history(history)
                    st.success("🤖 Gemini AI analyzed the data and saved the logic to history.")
        
        # --- APPLY MAPPING & VISUALIZE ---
        if intelligence:
            st.write(f"### Analysis for: **{selected_field}**")
            st.write(f"**Recommended Graph:** {intelligence['graph_type']}")
            
            # Map the raw data to standardized categories
            df["Standardized_Value"] = df[selected_field].map(intelligence['mapping']).fillna("Other")
            
            # Count the new standardized categories
            viz_data = df["Standardized_Value"].value_counts().reset_index()
            viz_data.columns = [selected_field, "Count"]
            
            # Render Graph
            graph_type = intelligence['graph_type']
            
            if "Bar" in graph_type:
                st.bar_chart(viz_data.set_index(selected_field))
            elif "Pie" in graph_type or "Donut" in graph_type:
                # Streamlit natively doesn't have pie chart, so we use Altair or just display dataframe
                # For simplicity here, showing a bar chart as fallback or you can integrate Plotly
                import plotly.express as px
                fig = px.pie(viz_data, values='Count', names=selected_field, hole=0.4 if "Donut" in graph_type else 0)
                st.plotly_chart(fig)
                
            with st.expander("Show AI Mapping Dictionary (Ready for Hardcoding)"):
                st.json(intelligence)

else:
    st.info("No data available for this entity. Please update the data loader.")
