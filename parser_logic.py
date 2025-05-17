# ------------------ parser_logic.py ------------------

import os
import re
import io
import uuid
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
from langdetect import detect
from pdf2image import convert_from_path
from llama_parse import LlamaParse
from openai import OpenAI
import openai

load_dotenv()

# Initialize LlamaParse
parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type="text"
)

# ---------- PDF Parsing ----------

def parse_pdf(file_path):
    try:
        documents = parser.load_data(file_path)
        full_text = "\n\n".join([doc.text for doc in documents if doc.text.strip()])
        print("[DEBUG] Parsed text length:", len(full_text))
        print("[DEBUG] Sample:", full_text[:500])
        return full_text.encode("utf-8", errors="replace").decode("utf-8")
    except Exception as e:
        print("[ERROR] Failed to parse PDF:", e)
        return ""

# ---------- Feature Detection ----------
def detect_language(text):
    try:
        return detect(text)
    except:
        return "Unknown"

def contains_tables(text):
    return bool(re.search(r"\|\s?.*\|\s?\n\|\s?-+", text))

def contains_images(text):
    return "![image]" in text or re.search(r"!\[.*?\]\(.*?\)", text)

# ---------- Full Page Rendered Images ----------
def extract_images_from_pdf(file_path, output_folder="images", poppler_path=None):
    os.makedirs(output_folder, exist_ok=True)
    images = convert_from_path(file_path, dpi=150, poppler_path=poppler_path)

    image_paths = []
    for i, img in enumerate(images):
        filename = f"{output_folder}/page_{i+1}_{uuid.uuid4().hex[:8]}.jpg"
        img.save(filename, "JPEG")
        image_paths.append(filename)

    return image_paths

# ---------- Embedded Image Extraction ----------
def extract_embedded_images(file_path, output_folder="embedded_images"):
    os.makedirs(output_folder, exist_ok=True)
    image_paths = []

    doc = fitz.open(file_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        if image_list:
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                image = Image.open(io.BytesIO(image_bytes))
                filename = f"{output_folder}/page{page_num+1}_img{img_index+1}_{uuid.uuid4().hex[:6]}.{image_ext}"
                image.save(filename)
                image_paths.append(filename)

    return image_paths

# ---------- AI Transformation with OpenAI ----------
def transform_markdown_with_gpt(markdown_text, prompt_type_or_custom=None):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    if not markdown_text.strip():
        return "⚠️ Error: Parsed markdown is empty. Please re-parse the document before running GPT transformation."

    # Handle either preset keyword or custom free-text prompt
    preset_prompts = {
        "table": "You are professional in analyzing and structuring documents. In the document, identify all tasks/questions and their respective answers. Structure them and convert the input into a well-structured CSV table. Consider a column for each answer per task/question. Take the exact formulation of each question and each answer. Make a column stating the correct answers. Be aware of correct CSV formatting and consider empty spaces if necessary. Separate all with semicolon. Encode in UTF-8, if you see Umlaute like ö,ä,ü,ß,... the transform them properly in oe,ae,ue,ss, etc.",
        "summary": "You are an expert document summarizer. Convert the input markdown into a well-structured executive summary.",
        "report": "You are a professional analyst. Turn the input markdown into a clear and concise report.",
        "article": "You are a skilled writer. Transform the input markdown into a well-written, engaging article."
    }

    prompt = preset_prompts.get(prompt_type_or_custom, prompt_type_or_custom or "You are a helpful assistant.")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": markdown_text}
        ],
        temperature=0.1
    )

    result = response.choices[0].message.content
    # Ensure UTF-8 encoded result with proper decoding of Umlaute etc.
    return result.encode("utf-8", errors="replace").decode("utf-8").strip()
