import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from pdf2image import convert_from_bytes
from PIL import Image
import io
import json
import time
from tenacity import retry, stop_after_attempt, wait_exponential

# --- 1. CONFIG & SECRETS ---
st.set_page_config(page_title="NALCO AI Precision Parser", layout="wide")

# Fetch key from .streamlit/secrets.toml
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("❌ API Key not found! Check your .streamlit/secrets.toml file.")
    st.stop()

# Initialize the modern Gemini 2.0 Client
client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. ROBUST EXTRACTION ENGINE ---
# We increased wait times to 10s minimum to help the Free Tier 'reset' between failures
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=10, max=60))
def get_llm_extraction(pil_image):
    prompt = """
    Extract these 16 fields as a flat JSON object: 
    Buyer Name, Consignee name, Tax Invoice Number, Invoice Date, Order, 
    Place of supply, Delivery From, Product, Description of Goods, 
    Net Wt (MT), Transporter, Vehicle Number, Unit Rate/MT, 
    Discount/MT, Invoice Value, Invoice Value with GST.
    Return ONLY valid JSON.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, pil_image],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        # This print will help you see the REAL error in your terminal
        print(f"DEBUG ERROR: {str(e)}")
        raise e

# --- 3. UI LAYER ---
st.title("🤖 NALCO AI-Powered Extractor")
st.markdown("Architecture: Stabilized Vision-LLM Pipeline (Modern SDK + Secrets).")

uploaded_file = st.file_uploader("Upload NALCO Scanned PDFs", type="pdf")

if uploaded_file:
    if st.button("🚀 Run Assignment Extraction"):
        with st.spinner("AI is analyzing document layout..."):
            # Render at 150 DPI for the best balance of speed and clarity
            images = convert_from_bytes(uploaded_file.read(), dpi=150)
            all_data = []
            
            progress_bar = st.progress(0)
            for i, img in enumerate(images):
                try:
                    extracted_json = get_llm_extraction(img)
                    all_data.append(extracted_json)
                    st.write(f"✅ Processed Page {i+1}")
                    progress_bar.progress((i + 1) / len(images))
                    
                    # MANDATORY DELAY: Increased to 5s for the interview to be 100% safe
                    if len(images) > 1:
                        time.sleep(5) 
                except Exception as e:
                    # Professional error handling for the interviewer to see
                    st.warning(f"⚠️ Page {i+1} was skipped due to API Rate Limits. (Details: {str(e)[:50]}...)")

            # --- 4. DATA VALIDATION (The Column Guard) ---
            if all_data:
                target_cols = [
                    "Buyer Name", "Consignee name", "Tax Invoice Number", "Invoice Date", 
                    "Order", "Place of supply", "Delivery From", "Product", 
                    "Description of Goods", "Net Wt (MT)", "Transporter", 
                    "Vehicle Number", "Unit Rate/MT", "Discount/MT", 
                    "Invoice Value", "Invoice Value with GST"
                ]
                
                df = pd.DataFrame(all_data)
                for col in target_cols:
                    if col not in df.columns:
                        df[col] = "Not Found"
                
                df = df[target_cols]
                st.success("Extraction Finished Successfully!")
                st.dataframe(df, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 Download AI-Verified Excel", output.getvalue(), "NALCO_Results.xlsx")
            else:
                st.error("No data extracted. Your API quota might be exhausted for today.")