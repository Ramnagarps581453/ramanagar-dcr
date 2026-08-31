import os
import glob
import subprocess
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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

# --- HELPER FUNCTION: DYNAMIC FONT INSTALLER ---
def install_custom_fonts():
    font_dir = os.path.expanduser("~/.local/share/fonts")
    os.makedirs(font_dir, exist_ok=True)
    font_files = glob.glob("*.ttf") + glob.glob("*.otf") + glob.glob("*.TTF") + glob.glob("*.OTF")
    if font_files:
        for font in font_files:
            subprocess.run(["cp", font, font_dir], check=False)
        subprocess.run(["fc-cache", "-f", "-v"], check=False)

# --- HELPER FUNCTION: AUTO-INCREMENT CR NUMBER ---
def get_next_cr_number(year):
    try:
        response = supabase.table("dcr_cases").select("cr_no").eq("reg_year", str(year)).execute()
        if response.data:
            max_cr = max([r["cr_no"] for r in response.data])
            return max_cr + 1
    except Exception:
        pass
    return 1

# --- PAGE CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="Ramanagar PS Crime Tracking",
    page_icon="🚔",
    layout="wide"
)

st.title("🚔 Ramanagar Police Station Crime Tracking System")

# --- ADMIN AUTHENTICATION & DEFAULT TAB SETTING ---
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

with st.sidebar:
    st.header("🔑 Access Control")
    if not st.session_state["is_admin"]:
        pin_input = st.text_input("Enter Admin PIN", type="password")
        if st.button("Login as Admin"):
            if pin_input == ADMIN_PIN:
                st.session_state["is_admin"] = True
                st.success("Admin access granted!")
                st.rerun()
            else:
                st.error("Incorrect PIN!")
    else:
        st.success("Mode: ADMIN (Full Access)")
        if st.button("Logout Admin"):
            st.session_state["is_admin"] = False
            st.rerun()

# Default to Case Status Monitoring for non-admins / mobile view
tab_order = ["📊 Case Status Monitoring", "📄 Upload & Manage DCR"] if not st.session_state["is_admin"] else ["📄 Upload & Manage DCR", "📊 Case Status Monitoring"]
tab_monitoring, tab_management = st.tabs(tab_order)

if not st.session_state["is_admin"]:
    tab2, tab1 = tab_monitoring, tab_management
else:
    tab1, tab2 = tab_monitoring, tab_management

# ==========================================
# TAB: CASE STATUS MONITORING (MOBILE OPTIMIZED PDF VIEWER)
# ==========================================
with tab2:
    st.subheader("Case Status Overview & Advanced Filters")

    # Dynamic Interactive Filters Section
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        filter_type = st.radio("Filter Case Type", ["ALL", "Heinous", "Non-Heinous"], horizontal=True)
    with f_col2:
        filter_io = st.radio("Filter IO", ["ALL", "SHO", "CPI", "DSP"], horizontal=True)
    with f_col3:
        filter_stage = st.radio("Filter Stage", ["ALL", "Under Investigation", "Under Scrutiny", "CC Pending", "UI Disposed"], horizontal=True)

    # Dynamic Data Query
    query = supabase.table("dcr_cases").select("*")
    if filter_type != "ALL":
        query = query.eq("case_type", filter_type)
    if filter_io != "ALL":
        query = query.eq("investigating_officer", filter_io)
    if filter_stage != "ALL":
        query = query.eq("stage", filter_stage)

    res = query.order("cr_no", desc=False).execute()
    filtered_records = res.data

    total_count = len(filtered_records) if filtered_records else 0

    # Total Cases Counter Summary Box
    st.metric(label="Total Cases Found", value=total_count)

    if filtered_records:
        df_status = pd.DataFrame(filtered_records)
        df_status.insert(0, "Sl. No.", range(1, len(df_status) + 1))
        
        if "sections" not in df_status.columns:
            df_status["sections"] = ""

        # Main Table Display
        st.dataframe(
            df_status.rename(columns={
                "cr_no": "CR No", "reg_year": "Year", "case_type": "Case Type",
                "investigating_officer": "IO", "sections": "Sections", "stage": "Stage Status",
                "scrutiny_officer": "With Officer", "pdf_url": "PDF Link"
            })[["Sl. No.", "CR No", "Year", "Case Type", "IO", "Sections", "Stage Status", "PDF Link"]],
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # Mobile Direct PDF Access & Case Selection
        st.subheader("📲 Mobile Quick PDF Viewer")
        selected_case_id = st.selectbox(
            "Select CR Number to open PDF directly on Mobile:",
            options=[r["id"] for r in filtered_records],
            format_func=lambda x: f"CR No: {[r for r in filtered_records if r['id']==x][0]['cr_no']}/{[r for r in filtered_records if r['id']==x][0]['reg_year']} - Sections: {[r for r in filtered_records if r['id']==x][0].get('sections', 'N/A')}"
        )
        
        selected_rec = [r for r in filtered_records if r["id"] == selected_case_id][0]
        pdf_url = selected_rec.get("pdf_url", "")

        c_btn, c_info = st.columns([1, 2])
        with c_btn:
            st.link_button("📄 Open DCR PDF Fullscreen", pdf_url, use_container_width=True)

        with st.expander("📱 Tap to Embed/Preview PDF on Screen", expanded=False):
            if pdf_url:
                components.html(
                    f'<iframe src="{pdf_url}" width="100%" height="600px" style="border:none;"></iframe>',
                    height=620
                )
            else:
                st.warning("No PDF URL available for this record.")

        st.divider()

        # Bulk & Single Case Editing Control Panel (Admin Only)
        if st.session_state["is_admin"]:
            st.subheader("⚙️ Bulk / Batch Update Cases")
            
            selected_case_ids = st.multiselect(
                "Select CR Numbers to update at once:",
                options=[r["id"] for r in filtered_records],
                format_func=lambda x: f"CR No: {[r for r in filtered_records if r['id']==x][0]['cr_no']}/{[r for r in filtered_records if r['id']==x][0]['reg_year']} (Current Stage: {[r for r in filtered_records if r['id']==x][0]['stage']})"
            )

            if selected_case_ids:
                b_col1, b_col2, b_col3 = st.columns(3)
                with b_col1:
                    new_case_type = st.selectbox("Update Case Type (Optional)", ["No Change", "Non-Heinous", "Heinous"])
                with b_col2:
                    new_io = st.selectbox("Update IO (Optional)", ["No Change", "SHO", "CPI", "DSP"])
                with b_col3:
                    new_stage = st.selectbox("Update Stage Status (Optional)", ["No Change", "Under Investigation", "Under Scrutiny", "CC Pending", "UI Disposed"])

                new_sections = st.text_input("Update Sections (Optional - Leave blank to keep existing)", placeholder="e.g. 302, 395 IPC")

                scrutiny_officer = ""
                if new_stage == "Under Scrutiny":
                    scrutiny_officer = st.radio("With Officer (Scrutiny)", ["CPI", "DSP", "APP", "PP"], horizontal=True)

                if st.button("Apply Bulk Updates"):
                    update_payload = {}
                    if new_case_type != "No Change": update_payload["case_type"] = new_case_type
                    if new_io != "No Change": update_payload["investigating_officer"] = new_io
                    if new_sections.strip() != "": update_payload["sections"] = new_sections.strip()
                    if new_stage != "No Change":
                        update_payload["stage"] = new_stage
                        update_payload["scrutiny_officer"] = scrutiny_officer

                    if update_payload:
                        for cid in selected_case_ids:
                            supabase.table("dcr_cases").update(update_payload).eq("id", cid).execute()
                        st.success(f"Updated {len(selected_case_ids)} records successfully!")
                        st.rerun()
                    else:
                        st.warning("Please select at least one field to change.")
    else:
        st.info("No cases matching the selected filters.")

# ==========================================
# TAB: UPLOAD & MANAGE DCR
# ==========================================
with tab1:
    st.subheader("Add / Upload New DCR File")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        reg_year = st.selectbox("Year", options=[str(y) for y in range(2024, 2031)], index=2)
    with col1:
        auto_cr = get_next_cr_number(reg_year)
        cr_no = st.number_input("CR No", value=auto_cr, step=1)
    with col3:
        case_type = st.radio("Case Type", ["Non-Heinous", "Heinous"], horizontal=True)

    col_io, col_sec, col_file = st.columns([1, 1, 2])
    with col_io:
        io_officer = st.radio("Investigating Officer (IO)", ["SHO", "CPI", "DSP"], horizontal=True)
    with col_sec:
        sections = st.text_input("IPC / Law Sections", placeholder="e.g. 302, 395 IPC")
    with col_file:
        uploaded_file = st.file_uploader("Upload Case File (.pdf or .docx)", type=["pdf", "docx"])

    # Duplicate CR Number Check
    existing_check = supabase.table("dcr_cases").select("id").eq("cr_no", int(cr_no)).eq("reg_year", str(reg_year)).execute()
    is_duplicate = len(existing_check.data) > 0

    if is_duplicate:
        st.error(f"⚠️ CR No {cr_no}/{reg_year} already exists in records! Duplicate numbers are blocked.")

    if st.button("Save & Upload to Cloud Vault", disabled=not st.session_state["is_admin"] or is_duplicate):
        if uploaded_file is None:
            st.error("Please upload a file first!")
        else:
            file_bytes = uploaded_file.getvalue()
            orig_name = uploaded_file.name
            pdf_filename = f"CR_{cr_no}_{reg_year}.pdf"

            try:
                if orig_name.endswith(".docx"):
                    st.info("Converting Word document to PDF on server...")
                    install_custom_fonts()

                    with open("temp.docx", "wb") as f:
                        f.write(file_bytes)
                    
                    subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "temp.docx"], check=True)
                    
                    with open("temp.pdf", "rb") as f:
                        final_pdf_bytes = f.read()
                        
                    if os.path.exists("temp.docx"): os.remove("temp.docx")
                    if os.path.exists("temp.pdf"): os.remove("temp.pdf")
                else:
                    final_pdf_bytes = file_bytes

                # Upload to Supabase Storage
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=pdf_filename,
                    file=final_pdf_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
                pdf_url = supabase.storage.from_(BUCKET_NAME).get_public_url(pdf_filename)

                # Insert to Supabase Database Table
                supabase.table("dcr_cases").insert({
                    "cr_no": int(cr_no),
                    "reg_year": str(reg_year),
                    "case_type": case_type,
                    "investigating_officer": io_officer,
                    "sections": sections,
                    "pdf_url": pdf_url,
                    "stage": "Under Investigation",
                }).execute()

                st.success(f"CR No {cr_no}/{reg_year} converted & saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving record: {e}")

    st.divider()
    st.subheader("All Saved DCR Files")
    
    response = supabase.table("dcr_cases").select("*").order("cr_no", desc=False).execute()
    records = response.data

    if records:
        df_upload = pd.DataFrame(records)
        df_upload.insert(0, "Sl. No.", range(1, len(df_upload) + 1))
        
        if "sections" not in df_upload.columns:
            df_upload["sections"] = ""

        st.dataframe(
            df_upload.rename(columns={
                "cr_no": "CR No", "reg_year": "Year", "case_type": "Case Type",
                "investigating_officer": "IO", "sections": "Sections",
                "stage": "Stage Status", "pdf_url": "PDF URL"
            })[["Sl. No.", "CR No", "Year", "Case Type", "IO", "Sections", "Stage Status", "PDF URL"]],
            use_container_width=True,
            hide_index=True
        )

        selected_case_id = st.selectbox(
            "Select Case Record to View/Edit/Delete:",
            options=[r["id"] for r in records],
            format_func=lambda x: f"CR No: {[r for r in records if r['id']==x][0]['cr_no']}/{[r for r in records if r['id']==x][0]['reg_year']}"
        )
        
        selected_rec = [r for r in records if r["id"] == selected_case_id][0]

        # Single Record Quick Modifications (IO / Case Type / Sections)
        if st.session_state["is_admin"]:
            with st.expander("✏️ Edit Selected Case Details"):
                e_col1, e_col2, e_col3 = st.columns(3)
                with e_col1:
                    edit_case_type = st.radio("Case Type", ["Non-Heinous", "Heinous"], index=0 if selected_rec.get("case_type") == "Non-Heinous" else 1, key=f"ct_{selected_case_id}")
                with e_col2:
                    io_options = ["SHO", "CPI", "DSP"]
                    io_idx = io_options.index(selected_rec.get("investigating_officer")) if selected_rec.get("investigating_officer") in io_options else 0
                    edit_io = st.radio("Investigating Officer", io_options, index=io_idx, key=f"io_{selected_case_id}")
                with e_col3:
                    edit_sections = st.text_input("Sections", value=selected_rec.get("sections", ""), key=f"sec_{selected_case_id}")
                
                if st.button("Save Case Details"):
                    supabase.table("dcr_cases").update({
                        "case_type": edit_case_type,
                        "investigating_officer": edit_io,
                        "sections": edit_sections
                    }).eq("id", selected_case_id).execute()
                    st.success("Case details updated successfully!")
                    st.rerun()

        col_v, col_d = st.columns([1, 4])
        with col_v:
            st.link_button("📄 Open / Download PDF", selected_rec["pdf_url"])
        with col_d:
            if st.button("🗑️ Delete Selected Case Record", disabled=not st.session_state["is_admin"]):
                pdf_name = f"CR_{selected_rec['cr_no']}_{selected_rec['reg_year']}.pdf"
                supabase.storage.from_(BUCKET_NAME).remove([pdf_name])
                supabase.table("dcr_cases").delete().eq("id", selected_case_id).execute()
                st.warning("Record deleted!")
                st.rerun()
