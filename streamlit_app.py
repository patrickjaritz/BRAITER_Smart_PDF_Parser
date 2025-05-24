

# ------------------ app.py ------------------

import streamlit as st
import tempfile
import io
import json
import pandas as pd
from docx import Document
from PIL import Image

from parser_logic import (
    parse_pdf,
    detect_language,
    contains_tables,
    contains_images,
    extract_images_from_pdf,
    extract_embedded_images,
    transform_markdown_with_gpt
)

# --- Constants for UI and Processing ---
APP_TITLE = "📄 BRAITER Smart PDF Parser (with Language & Table Detection)"
FILE_UPLOAD_LABEL = "Upload your PDF"
GPT_MIN_TEXT_LENGTH = 100 # Minimum characters in parsed text to enable GPT features

# Error prefixes from parser_logic.py
ERROR_PREFIX = "⚠️ Error:"
INFO_PREFIX = "ℹ️ Info:" # For informational messages that might not be errors but need attention

# --- Helper Functions ---

def display_image_gallery(image_paths: list[str], caption_prefix: str, num_columns: int = 3):
    """Displays a gallery of images with download buttons."""
    if not image_paths:
        st.info(f"No {caption_prefix.lower()} images found.")
        return

    st.markdown(f"### 🖼 {caption_prefix} Images Gallery")
    cols = st.columns(num_columns)
    for i, img_path in enumerate(image_paths):
        col = cols[i % num_columns]
        try:
            img = Image.open(img_path)
            col.image(img, use_column_width=True)
            with open(img_path, "rb") as f_img:
                col.download_button(
                    label=f"Download {os.path.basename(img_path)}",
                    data=f_img.read(), # Read here as file object might close
                    file_name=os.path.basename(img_path),
                    mime="image/jpeg" if img_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
                )
        except FileNotFoundError:
            col.error(f"Image not found: {os.path.basename(img_path)}")
        except Exception as e:
            col.error(f"Error loading {os.path.basename(img_path)}: {e}")


def handle_export_buttons(transformed_text: str):
    """Displays various download buttons for the transformed text."""
    st.download_button("📥 Download as TXT", transformed_text, file_name="ai_output.txt")
    st.download_button("📥 Download as Markdown (.md)", transformed_text, file_name="ai_output.md")

    # DOCX export
    try:
        docx_buffer = io.BytesIO()
        doc = Document()
        for line in transformed_text.split("\n"):
            doc.add_paragraph(line)
        doc.save(docx_buffer)
        docx_buffer.seek(0)
        st.download_button("📥 Download as Word (.docx)", docx_buffer, file_name="ai_output.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as e:
        st.error(f"Error creating DOCX: {e}")

    # JSON, CSV, Excel export (attempt to parse as JSON for structured data)
    try:
        json_obj = json.loads(transformed_text)
    except json.JSONDecodeError:
        # If not valid JSON, treat the whole text as a single piece of data for export
        json_obj = {"ai_output": transformed_text}

    try:
        if isinstance(json_obj, list) and all(isinstance(item, dict) for item in json_obj):
            df = pd.DataFrame(json_obj)
        elif isinstance(json_obj, dict):
            df = pd.DataFrame([json_obj])
        else: # Fallback for non-structured JSON (e.g. a simple string or number in JSON)
            df = pd.DataFrame({"AI Output": [str(json_obj)]}) # Ensure it's a string

        if df is not None and not df.empty:
            st.markdown("### 📊 Table Preview (from AI Output)")
            st.dataframe(df.head()) # Show only a preview

            json_export_data = json.dumps(json_obj, indent=2).encode("utf-8")
            st.download_button("📥 Download as JSON", json_export_data, file_name="ai_output.json", mime="application/json")

            csv_export_data = "\ufeff" + df.to_csv(index=False, sep=";").encode("utf-8")
            st.download_button("📥 Download as CSV (semicolon)", csv_export_data, file_name="ai_output.csv", mime="text/csv")

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='AI_Output')
            excel_buffer.seek(0)
            st.download_button(label="📥 Download as Excel (.xlsx)", data=excel_buffer, file_name="ai_output.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"Error preparing data for Table/JSON/CSV/Excel export: {e}")
        # Still offer to download the raw transformed text as JSON if parsing failed at DataFrame stage
        if not isinstance(json_obj, dict) or json_obj.get("ai_output") != transformed_text:
             st.download_button("📥 Download Raw AI Output as JSON", json.dumps({"raw_ai_output": transformed_text}).encode("utf-8"),
                                file_name="ai_output_raw.json", mime="application/json")


# --- Main App Logic ---
st.set_page_config(page_title=APP_TITLE)
st.title(APP_TITLE)

uploaded_file = st.file_uploader(FILE_UPLOAD_LABEL, type=["pdf"])

if uploaded_file:
    # Manage session state for parsed text to avoid re-parsing on every interaction
    if "last_file_name" not in st.session_state or uploaded_file.name != st.session_state["last_file_name"]:
        st.session_state.pop("parsed_text_or_error", None) # Clear previous results
        st.session_state["last_file_name"] = uploaded_file.name
        st.session_state["temp_pdf_path"] = None # Reset temp file path

    # Create a temporary file for the PDF
    if not st.session_state.get("temp_pdf_path"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue()) # Use getvalue() for UploadedFile
            st.session_state["temp_pdf_path"] = tmp.name
    
    pdf_path = st.session_state["temp_pdf_path"]

    # Parse PDF if not already parsed or if file changed
    if "parsed_text_or_error" not in st.session_state:
        with st.spinner("Parsing PDF. Please wait..."):
            parsed_text_or_error = parse_pdf(pdf_path)
            st.session_state["parsed_text_or_error"] = parsed_text_or_error
            if not parsed_text_or_error.startswith(ERROR_PREFIX):
                st.success("✅ Parsing Complete")
            else:
                st.error(parsed_text_or_error) # Show parsing error

    parsed_text_or_error = st.session_state["parsed_text_or_error"]

    # --- Display results if parsing was successful ---
    if not parsed_text_or_error.startswith(ERROR_PREFIX):
        parsed_text = parsed_text_or_error # It's actual text, not an error message

        # Metadata Section
        with st.expander("📄 Document Metadata", expanded=True):
            lang = detect_language(parsed_text)
            has_tables_val = contains_tables(parsed_text)
            has_images_val = contains_images(parsed_text)
            st.markdown(f"**🌍 Language Detected:** `{lang}`")
            st.markdown(f"**📊 Tables Detected (Markdown):** `{has_tables_val}`")
            st.markdown(f"**🖼 Images Detected (Markdown):** `{has_images_val}`")

        if st.checkbox("🔍 Show full parsed Markdown"):
            st.text_area("Full Parsed Markdown", parsed_text, height=300)

        # GPT Transformation Section (only if parsed text is substantial)
        if len(parsed_text.strip()) >= GPT_MIN_TEXT_LENGTH:
            with st.expander("🤖 Transform Markdown with GPT"):
                st.markdown("Use OpenAI to enhance your parsed document.")
                use_custom_prompt = st.checkbox("Use custom prompt", value=False)

                if use_custom_prompt:
                    user_prompt_input = st.text_area("Enter your custom prompt:")
                else:
                    transform_type = st.selectbox("Choose output type:", ["table", "summary", "report", "article"])
                    user_prompt_input = None # Will use transform_type as key for preset prompt

                if st.button("Transform with GPT"):
                    with st.spinner("Processing with GPT..."):
                        transformed_output = transform_markdown_with_gpt(parsed_text, user_prompt_input or transform_type)
                        
                        if transformed_output.startswith(ERROR_PREFIX):
                            st.error(transformed_output)
                        elif transformed_output.startswith(INFO_PREFIX):
                            st.info(transformed_output)
                            st.markdown("### ✨ Transformed Document (Partial/Info)")
                            st.text_area("Output", transformed_output, height=300)
                        else:
                            st.success("✅ AI Transformation Complete")
                            st.markdown("### ✨ Transformed Document")
                            st.text_area("Output", transformed_output, height=300)
                            handle_export_buttons(transformed_output)
        else:
            st.info(f"Parsed text is too short (less than {GPT_MIN_TEXT_LENGTH} characters). GPT transformation features are disabled.")

        # Image Extraction Galleries (using the helper function)
        # Note: extract_images_from_pdf and extract_embedded_images might return empty lists or lists of paths
        # The display_image_gallery function handles the "No images found" case.
        
        page_images = extract_images_from_pdf(pdf_path) # Uses default output folder from parser_logic
        display_image_gallery(page_images, "Extracted Page")

        embedded_images = extract_embedded_images(pdf_path) # Uses default output folder
        display_image_gallery(embedded_images, "Embedded")

    else:
        # This case is if parse_pdf itself returned an error string already displayed
        # No further processing on parsed_text is done here.
        # Could add a message like "Resolve parsing error to see more options."
        pass # Error already shown when "parsed_text_or_error" was set

else:
    st.info("Upload a PDF file to begin processing.")

# Cleanup for temporary PDF file (optional, as OS might handle it, but good practice)
# This is tricky with Streamlit's execution model. A more robust way would be a session cleanup mechanism.
# For now, relying on OS to clean /tmp or manual cleanup if files are explicitly not deleted by NamedTemporaryFile.
# If delete=True was used with NamedTemporaryFile, file is deleted once closed.
# Since we use delete=False and store path in session, it persists.
# A proper cleanup would involve st.on_session_end or similar, if available and suitable.
