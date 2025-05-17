

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

st.set_page_config(page_title="📄 BRAITER Smart PDF Parser")
st.title("📄 BRAITER Smart PDF Parser")
st.write(
    "Now with automatic language & table detection!"
)

uploaded_file = st.file_uploader("Upload your PDF", type=["pdf"])

# === Handle File Upload and Parsing ===
if uploaded_file:
    if "last_file_name" not in st.session_state or uploaded_file.name != st.session_state["last_file_name"]:
        st.session_state.pop("parsed_text", None)
        st.session_state["last_file_name"] = uploaded_file.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        path = tmp.name

    if "parsed_text" not in st.session_state:
        st.info("Parsing PDF. Please wait...")
        parsed_text = parse_pdf(path)
        st.session_state["parsed_text"] = parsed_text
        st.success("✅ Parsing Complete")
    else:
        parsed_text = st.session_state["parsed_text"]

    # Metadata
    lang = detect_language(parsed_text)
    has_tables = contains_tables(parsed_text)
    has_images = contains_images(parsed_text)

    st.markdown(f"**🌍 Language Detected:** `{lang}`")
    st.markdown(f"**📊 Tables Detected:** `{has_tables}`")
    st.markdown(f"**🖼 Images Detected (Markdown):** `{has_images}`")

    if st.checkbox("🔍 Show full parsed Markdown"):
        st.text_area("Full Parsed Markdown", parsed_text, height=300)

    # === GPT Transformation ===
    if len(parsed_text.strip()) > 100:
        with st.expander("🤖 Transform Markdown with GPT"):
            st.markdown("Use OpenAI to enhance your parsed document.")
            use_custom_prompt = st.checkbox("Use custom prompt", value=False)

            if use_custom_prompt:
                user_prompt = st.text_area("Enter your custom prompt:")
            else:
                transform_type = st.selectbox("Choose output type:", ["table", "summary", "report", "article"])
                user_prompt = None

            if st.button("Transform with GPT"):
                with st.spinner("Processing with GPT..."):
                    transformed = transform_markdown_with_gpt(parsed_text, user_prompt or transform_type)
                    st.success("✅ AI Transformation Complete")
                    st.markdown("### ✨ Transformed Document")
                    st.text_area("Output", transformed, height=300)

                    # Export Options
                    st.download_button("📥 Download as TXT", transformed, file_name="ai_output.txt")
                    st.download_button("📥 Download as Markdown (.md)", transformed, file_name="ai_output.md")

                    # DOCX export
                    docx_buffer = io.BytesIO()
                    doc = Document()
                    for line in transformed.split("\n"):
                        doc.add_paragraph(line)
                    doc.save(docx_buffer)
                    docx_buffer.seek(0)
                    st.download_button("📥 Download as Word (.docx)", docx_buffer, file_name="ai_output.docx",
                                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

                    # JSON + CSV + Excel export
                    try:
                        parsed_json = json.loads(transformed)
                        json_obj = parsed_json
                    except json.JSONDecodeError:
                        json_obj = {"ai_output": transformed}

                    if isinstance(json_obj, list) and all(isinstance(item, dict) for item in json_obj):
                        df = pd.DataFrame(json_obj)
                    elif isinstance(json_obj, dict):
                        df = pd.DataFrame([json_obj])
                    else:
                        df = pd.DataFrame({"AI Output": [transformed]})

                    # Optional Table Preview
                    if df is not None and len(df.columns) > 1:
                        st.markdown("### 📊 Table Preview")
                        st.dataframe(df)

                    # JSON
                    json_buffer = json.dumps(json_obj, indent=2).encode("utf-8")
                    st.download_button("📥 Download as JSON", json_buffer, file_name="ai_output.json",
                                       mime="application/json")

                    # CSV
                    csv_buffer = "\ufeff" + df.to_csv(index=False, sep=";")
                    csv_buffer = csv_buffer.encode("utf-8")

                    st.download_button("📥 Download as CSV (semicolon)", csv_buffer, file_name="ai_output.csv",
                                       mime="text/csv")

                    # Excel
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='AI_Output')
                        excel_buffer.seek(0)

                    st.download_button(
                        label="📥 Download as Excel (.xlsx)",
                        data=excel_buffer,
                        file_name="ai_output.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


    else:
        st.warning("Parsed text too short or empty — please upload a valid PDF first.")

    # === Page Rendered Images ===
    image_paths = extract_images_from_pdf(path)
    if image_paths:
        st.markdown("### 🖼 Extracted Page Images Gallery")
        cols = st.columns(3)
        for i, img_path in enumerate(image_paths):
            col = cols[i % 3]  # Cycle through columns
            with col:
                st.image(Image.open(img_path), use_container_width=True)
                with open(img_path, "rb") as f:
                    st.download_button(
                        label=f"Download {img_path.split('/')[-1]}",
                        data=f,
                        file_name=img_path.split('/')[-1],
                        mime="image/jpeg"
                    )
    else:
        st.info("No full-page images found.")

    # === Embedded Images ===
    embedded = extract_embedded_images(path)
    if embedded:
        st.markdown("### 🖼 Embedded Images Gallery")
        cols = st.columns(3)
        for i, img_path in enumerate(embedded):
            col = cols[i % 3]
            with col:
                st.image(Image.open(img_path), use_container_width=True)
                with open(img_path, "rb") as f:
                    st.download_button(
                        label=f"Download {img_path.split('/')[-1]}",
                        data=f,
                        file_name=img_path.split('/')[-1],
                        mime="image/jpeg" if img_path.endswith(".jpg") else "image/png"
                    )
    else:
        st.info("No embedded images found.")
