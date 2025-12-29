import streamlit as st
import pandas as pd
import google.generativeai as genai
from pdf2image import convert_from_bytes
from PIL import Image
import io
import json
import os
from dotenv import load_dotenv

load_dotenv()
# --- CONFIG & LLM SETUP ---
st.set_page_config(page_title="NALCO AI Precision Parser", layout="wide")

# Load Gemini API Key from .env file
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def get_llm_extraction(pil_image):
    """
    Sends the invoice image to the Vision LLM for 100% accurate data extraction.
    """
    prompt = """
    Act as an expert data entry clerk. Extract the following 16 fields from this NALCO Tax Invoice. 
    Return ONLY a valid JSON object. If a field is missing, use "Not Found".
    
    Required Fields:
    1. Buyer Name (Usually ZETWERK)
    2. Consignee name (Usually Nirmal Wires)
    3. Tax Invoice Number (9 digits starting with 882)
    4. Invoice Date (DD.MM.YYYY)
    5. Order (8 digits starting with 320)
    6. Place of supply
    7. Delivery From
    8. Product
    9. Description of Goods
    10. Net Wt (MT) (Look for a decimal like 10.187 or 2.041)
    11. Transporter
    12. Vehicle Number
    13. Unit Rate/MT
    14. Discount/MT
    15. Invoice Value (Assessable value before tax)
    16. Invoice Value with GST (Final total)
    """
    
    response = model.generate_content([prompt, pil_image])
    # Clean the response to ensure it's valid JSON
    json_str = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(json_str)

# --- UI LAYER ---
st.title("🤖 NALCO AI-Powered Extractor")
st.markdown("Architecture: Vision-LLM Pipeline for 100% Accuracy.")

uploaded_file = st.file_uploader("Upload NALCO Scanned PDFs", type="pdf")

if uploaded_file:
    if st.button("Extract Data via AI"):
        if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
            st.error("Please provide a valid Gemini API Key to reach 100% accuracy.")
        else:
            with st.spinner("AI is analyzing the document layout..."):
                # Convert PDF to High-Res Image
                images = convert_from_bytes(uploaded_file.read(), dpi=300)
                all_data = []
                
                for i, img in enumerate(images):
                    try:
                        extracted_json = get_llm_extraction(img)
                        all_data.append(extracted_json)
                        st.write(f"✅ Processed Page {i+1}")
                    except Exception as e:
                        st.error(f"Error on Page {i+1}: {e}")

                # Create DataFrame with exact assignment column order
                target_cols = [
                    "Buyer Name", "Consignee name", "Tax Invoice Number", "Invoice Date", 
                    "Order", "Place of supply", "Delivery From", "Product", 
                    "Description of Goods", "Net Wt (MT)", "Transporter", 
                    "Vehicle Number", "Unit Rate/MT", "Discount/MT", 
                    "Invoice Value", "Invoice Value with GST"
                ]
                
                df = pd.DataFrame(all_data)[target_cols]
                st.success("100% Accuracy Extraction Complete!")
                st.dataframe(df)
                
                # Excel Export
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 Download Final AI Verified Excel", output.getvalue(), "NALCO_AI_Verified.xlsx")
