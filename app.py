import os
import subprocess
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# --- SUPABASE INITIALIZATION ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL", "https://vdfcmwpnqhqllkiohbth.supabase.co")
    key = st.secrets.get("SUPABASE_KEY", "sb_publishable_UHMnVxY7RS0Gz1jYCFQyrg_1-pla6jU")
    return create_client(url, key)

supabase = init_supabase()
BUCKET_NAME = "dcr_vault"
ADMIN_PIN = "1234"

# --- PAGE SETUP ---
st.set_page_config(page_title="Ramanagar PS Crime Tracking", page_icon="🚔", layout="wide")
st.title("🚔 Ramanagar Police Station Crime Tracking System")

# ... [Keep Sidebar Authentication Code Here] ...

# --- FILE UPLOADER WITH AUTO PDF CONVERSION ---
uploaded_file = st.file_uploader("Upload Case File (.pdf or .docx)", type=["pdf", "docx"])

if st.button("Save & Upload to Cloud Vault"):
    if uploaded_file is None:
        st.error("Please select a file first!")
    else:
        file_bytes = uploaded_file.getvalue()
        orig_name = uploaded_file.name
        pdf_filename = f"CR_{cr_no}_{reg_year}.pdf"
        
        # If user uploads DOCX, convert to PDF using LibreOffice on the server
        if orig_name.endswith(".docx"):
            st.info("Converting Word document to PDF...")
            
            # Save temporary docx file
            with open("temp.docx", "wb") as f:
                f.write(file_bytes)
            
            # Run LibreOffice headless conversion
            subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "temp.docx"], check=True)
            
            # Read converted PDF bytes
            with open("temp.pdf", "rb") as f:
                final_pdf_bytes = f.read()
                
            # Clean up temp files
            if os.path.exists("temp.docx"): os.remove("temp.docx")
            if os.path.exists("temp.pdf"): os.remove("temp.pdf")
        else:
            final_pdf_bytes = file_bytes

        # Upload final PDF to Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=pdf_filename,
            file=final_pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        pdf_url = supabase.storage.from_(BUCKET_NAME).get_public_url(pdf_filename)

        # Save metadata to database
        supabase.table("dcr_cases").insert({
            "cr_no": int(cr_no),
            "reg_year": str(reg_year),
            "case_type": case_type,
            "investigating_officer": io_officer,
            "pdf_url": pdf_url,
            "stage": "Under Investigation"
        }).execute()

        st.success(f"CR No {cr_no}/{reg_year} converted and uploaded as PDF!")
        st.rerun()
