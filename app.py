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

# --- AUTHENTICATION ---
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

with st.sidebar:
    st.header("🔑 Access Control")
    if not st.session_state["is_admin"]:
        pin_input = st.text_input("Enter Admin PIN", type="password")
        if st.button("Login as Admin"):
            if pin_input == ADMIN_PIN:
                st.session_state["is_admin"] = True
                st.success("Admin granted!")
                st.rerun()
            else:
                st.error("Incorrect PIN!")
    else:
        st.success("Mode: ADMIN")
        if st.button("Logout Admin"):
            st.session_state["is_admin"] = False
            st.rerun()

tab1, tab2 = st.tabs(["📄 Upload & Manage DCR", "📊 Case Status Monitoring"])

# --- TAB 1: UPLOAD & MANAGE DCR ---
with tab1:
    st.subheader("Add / Upload New DCR File")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        cr_no = st.number_input("CR No", value=1, step=1)
    with col2:
        reg_year = st.selectbox("Year", options=[str(y) for y in range(2024, 2031)], index=2)
    with col3:
        case_type = st.radio("Case Type", ["Non-Heinous", "Heinous"], horizontal=True)

    col_io, col_file = st.columns([1, 2])
    with col_io:
        io_officer = st.radio("Investigating Officer (IO)", ["SHO", "CPI", "DSP"], horizontal=True)
    with col_file:
        uploaded_file = st.file_uploader("Upload Case File (.pdf or .docx)", type=["pdf", "docx"])

    if st.button("Save & Upload to Cloud Vault", disabled=not st.session_state["is_admin"]):
        if uploaded_file is None:
            st.error("Please select a file first!")
        else:
            file_bytes = uploaded_file.getvalue()
            orig_name = uploaded_file.name
            pdf_filename = f"CR_{cr_no}_{reg_year}.pdf"

            try:
                # Automatic Word (.docx) to PDF Conversion
                if orig_name.endswith(".docx"):
                    st.info("Converting Word document to PDF on server...")
                    with open("temp.docx", "wb") as f:
                        f.write(file_bytes)
                    
                    subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "temp.docx"], check=True)
                    
                    with open("temp.pdf", "rb") as f:
                        final_pdf_bytes = f.read()
                        
                    if os.path.exists("temp.docx"): os.remove("temp.docx")
                    if os.path.exists("temp.pdf"): os.remove("temp.pdf")
                else:
                    final_pdf_bytes = file_bytes

                # 1. Upload final PDF to Supabase Storage
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=pdf_filename,
                    file=final_pdf_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
                pdf_url = supabase.storage.from_(BUCKET_NAME).get_public_url(pdf_filename)

                # 2. Insert record into Supabase Table
                supabase.table("dcr_cases").insert({
                    "cr_no": int(cr_no),
                    "reg_year": str(reg_year),
                    "case_type": case_type,
                    "investigating_officer": io_officer,
                    "pdf_url": pdf_url,
                    "stage": "Under Investigation",
                }).execute()

                st.success(f"CR No {cr_no}/{reg_year} saved and uploaded as PDF!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving record: {e}")

    st.divider()
    st.subheader("All Saved DCR Files")

    response = supabase.table("dcr_cases").select("*").order("cr_no", desc=False).execute()
    records = response.data

    if records:
        df = pd.DataFrame(records)
        st.dataframe(
            df[["cr_no", "reg_year", "case_type", "investigating_officer", "stage", "pdf_url"]],
            use_container_width=True,
        )

        selected_id = st.selectbox(
            "Select Case Record to Manage:",
            options=[r["id"] for r in records],
            format_func=lambda x: f"CR No: {[r for r in records if r['id']==x][0]['cr_no']}/{[r for r in records if r['id']==x][0]['reg_year']}",
        )

        selected_rec = [r for r in records if r["id"] == selected_id][0]

        col_v, col_d = st.columns([1, 4])
        with col_v:
            st.link_button("📄 Open PDF Document", selected_rec["pdf_url"])
        with col_d:
            if st.button("🗑️ Delete Selected Case Record", disabled=not st.session_state["is_admin"]):
                pdf_name = f"CR_{selected_rec['cr_no']}_{selected_rec['reg_year']}.pdf"
                supabase.storage.from_(BUCKET_NAME).remove([pdf_name])
                supabase.table("dcr_cases").delete().eq("id", selected_id).execute()
                st.warning("Record deleted!")
                st.rerun()

# --- TAB 2: MONITORING ---
with tab2:
    st.subheader("Case Status Overview & Filters")
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        filter_type = st.radio("Filter Case Type", ["ALL", "Heinous", "Non-Heinous"], horizontal=True)
    with f_col2:
        filter_io = st.radio("Filter IO", ["ALL", "SHO", "CPI", "DSP"], horizontal=True)
    with f_col3:
        filter_stage = st.radio(
            "Filter Stage",
            ["ALL", "Under Investigation", "Under Scrutiny", "CC Pending", "UI Disposed"],
            horizontal=True,
        )

    query = supabase.table("dcr_cases").select("*")
    if filter_type != "ALL":
        query = query.eq("case_type", filter_type)
    if filter_io != "ALL":
        query = query.eq("investigating_officer", filter_io)
    if filter_stage != "ALL":
        query = query.eq("stage", filter_stage)

    res = query.order("cr_no", desc=False).execute()
    filtered_records = res.data

    if filtered_records:
        df_status = pd.DataFrame(filtered_records)
        st.dataframe(
            df_status[["cr_no", "reg_year", "case_type", "investigating_officer", "stage", "scrutiny_officer"]],
            use_container_width=True,
        )

        st.divider()
        st.subheader("Update Case Stage Status")
        case_to_update = st.selectbox(
            "Select Case to Update:",
            options=[r["id"] for r in filtered_records],
            format_func=lambda x: f"CR No: {[r for r in filtered_records if r['id']==x][0]['cr_no']}/{[r for r in filtered_records if r['id']==x][0]['reg_year']}",
        )

        u_col1, u_col2 = st.columns(2)
        with u_col1:
            new_stage = st.radio(
                "Select New Stage Status",
                ["Under Investigation", "Under Scrutiny", "CC Pending", "UI Disposed"],
            )
        with u_col2:
            scrutiny_officer = ""
            if new_stage == "Under Scrutiny":
                scrutiny_officer = st.radio("With Officer (Scrutiny)", ["CPI", "DSP", "APP", "PP"], horizontal=True)

        if st.button("Save Status Changes", disabled=not st.session_state["is_admin"]):
            supabase.table("dcr_cases").update({
                "stage": new_stage,
                "scrutiny_officer": scrutiny_officer,
            }).eq("id", case_to_update).execute()
            st.success("Case status updated successfully!")
            st.rerun()
