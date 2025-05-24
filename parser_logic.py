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
import logging

load_dotenv()

# --- Setup Logging ---
logger = logging.getLogger(__name__)
# Basic configuration for logging (can be expanded in a central setup)
# To see logger output, you might need to configure the root logger in the main app or calling script
# For now, this sets a default handler if no configuration is found.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --- Constants ---
DEFAULT_RENDERED_IMAGES_FOLDER = "images"
DEFAULT_EMBEDDED_IMAGES_FOLDER = "embedded_images"
DEFAULT_IMAGE_CONVERSION_DPI = 150
# UUID length for filenames - just for brevity, not a security feature
UUID_SHORT_LENGTH_PAGE = 8
UUID_SHORT_LENGTH_EMBEDDED = 6


# --- LlamaParse Initialization ---
# Initialize LlamaParse
# It's good practice to check if the API key is available
llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
if not llama_api_key:
    logger.warning("LLAMA_CLOUD_API_KEY not found in environment variables. LlamaParse initialization might fail or use a default.")
# It might be better to raise an error here or handle it gracefully if the key is essential for all operations.

parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type="text"
)

# ---------- PDF Parsing ----------

def parse_pdf(file_path: str) -> str:
    """
    Parses the PDF file at the given path using LlamaParse.

    Args:
        file_path: The local path to the PDF file.

    Returns:
        The extracted text content as a single string.
        Returns an error message string starting with "⚠️ Error:" if parsing fails.
    """
    if not llama_api_key: # Check if LlamaParse key was loaded
        return "⚠️ Error: LLAMA_CLOUD_API_KEY not configured. PDF parsing cannot proceed."
    try:
        documents = parser.load_data(file_path)
        full_text = "\n\n".join([doc.text for doc in documents if doc.text and doc.text.strip()])
        # The encode-decode might be an attempt to clean up potential bad characters from parsing.
        # However, Python strings are Unicode, so direct use is usually fine.
        # If specific encoding issues are observed, they should be handled more directly.
        # For now, retaining it but noting it as a point for future investigation if issues arise.
        cleaned_text = full_text.encode("utf-8", errors="replace").decode("utf-8")
        logger.debug(f"Parsed PDF '{file_path}'. Text length: {len(cleaned_text)}. Sample: {cleaned_text[:200]}")
        return cleaned_text
    except openai.APIError as e:  # Assuming LlamaParse might raise errors similar to OpenAI's or wraps them.
        logger.error(f"API error during PDF parsing with LlamaParse for '{file_path}': {e}", exc_info=True)
        return f"⚠️ Error: PDF parsing failed due to an API issue (LlamaParse). Details: {e}"
    except Exception as e:
        logger.error(f"Failed to parse PDF '{file_path}': {e}", exc_info=True)
        return f"⚠️ Error: Failed to parse PDF. The file might be corrupted, password-protected, or an unexpected error occurred. Details: {e}"

# ---------- Feature Detection ----------
def detect_language(text: str) -> str:
    """
    Detects the language of the given text.

    Args:
        text: The input text.

    Returns:
        The detected language code (e.g., "en", "de") or "Unknown" if detection fails.
    """
    if not text or not text.strip():
        return "Unknown (empty input)"
    try:
        return detect(text)
    except Exception as e: # langdetect can sometimes fail on very short or ambiguous texts
        logger.warning(f"Language detection failed: {e}. Text sample: '{text[:100]}'", exc_info=True)
        return "Unknown"

def contains_tables(text: str) -> bool:
    """
    Checks if the text likely contains Markdown-like table structures.

    Args:
        text: The input text.

    Returns:
        True if table patterns are found, False otherwise.
    """
    if not text:
        return False
    # This regex looks for a common Markdown table pattern (header row with separators)
    return bool(re.search(r"\|\s?.*\|\s?\n\|\s?-+", text))

def contains_images(text: str) -> bool:
    """
    Checks if the text contains Markdown image references.

    Args:
        text: The input text.

    Returns:
        True if Markdown image patterns are found, False otherwise.
    """
    if not text:
        return False
    # Looks for "!alt[text](url)" or just "![image]" which LlamaParse might produce
    return "![image]" in text or bool(re.search(r"!\[.*?\]\(.*?\)", text))

# ---------- Full Page Rendered Images ----------
def extract_images_from_pdf(file_path: str, output_folder: str = DEFAULT_RENDERED_IMAGES_FOLDER, poppler_path: str = None) -> list[str]:
    """
    Extracts full-page rendered images from a PDF.
    Each page is converted to an image.

    Args:
        file_path: Path to the PDF file.
        output_folder: Folder to save extracted images. Defaults to DEFAULT_RENDERED_IMAGES_FOLDER.
        poppler_path: Optional path to Poppler binaries (if not in system PATH).

    Returns:
        A list of paths to the saved images. Returns empty list on failure or if no images.
    """
    os.makedirs(output_folder, exist_ok=True)
    image_paths = []
    try:
        images = convert_from_path(file_path, dpi=DEFAULT_IMAGE_CONVERSION_DPI, poppler_path=poppler_path)
        for i, img in enumerate(images):
            # Using a short UUID to ensure unique filenames
            filename = f"{output_folder}/page_{i+1}_{uuid.uuid4().hex[:UUID_SHORT_LENGTH_PAGE]}.jpg"
            img.save(filename, "JPEG")
            image_paths.append(filename)
        logger.info(f"Extracted {len(image_paths)} page images from '{file_path}' to '{output_folder}'.")
    except Exception as e:
        logger.error(f"Error extracting page images from PDF '{file_path}': {e}", exc_info=True)
        # Optionally, could return a specific error message or raise exception
    return image_paths

# ---------- Embedded Image Extraction ----------
def extract_embedded_images(file_path: str, output_folder: str = DEFAULT_EMBEDDED_IMAGES_FOLDER) -> list[str]:
    """
    Extracts embedded images directly from the PDF content using PyMuPDF (fitz).

    Args:
        file_path: Path to the PDF file.
        output_folder: Folder to save extracted images. Defaults to DEFAULT_EMBEDDED_IMAGES_FOLDER.

    Returns:
        A list of paths to the saved images. Returns empty list on failure or if no images.
    """
    os.makedirs(output_folder, exist_ok=True)
    image_paths = []
    try:
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
                # Using a short UUID for unique filenames
                filename = f"{output_folder}/page{page_num+1}_img{img_index+1}_{uuid.uuid4().hex[:UUID_SHORT_LENGTH_EMBEDDED]}.{image_ext}"
                image.save(filename)
                image_paths.append(filename)
        logger.info(f"Extracted {len(image_paths)} embedded images from '{file_path}' to '{output_folder}'.")
    except Exception as e:
        logger.error(f"Error extracting embedded images from PDF '{file_path}': {e}", exc_info=True)
        # Optionally, could return a specific error message or raise exception
    finally:
        if 'doc' in locals() and doc:
            doc.close()
    return image_paths

# ---------- AI Transformation with OpenAI ----------

# Static preset prompts dictionary
PRESET_GPT_PROMPTS = {
    "table": "You are professional in analyzing and structuring documents. In the document, identify all tasks/questions and their respective answers. Structure them and convert the input into a well-structured CSV table. Consider a column for each answer per task/question. Take the exact formulation of each question and each answer. Make a column stating the correct answers. Be aware of correct CSV formatting and consider empty spaces if necessary. Separate all with semicolon. Encode in UTF-8, if you see Umlaute like ö,ä,ü,ß,... the transform them properly in oe,ae,ue,ss, etc.",
    "summary": "You are an expert document summarizer. Convert the input markdown into a well-structured executive summary.",
    "report": "You are a professional analyst. Turn the input markdown into a clear and concise report.",
    "article": "You are a skilled writer. Transform the input markdown into a well-written, engaging article."
}
DEFAULT_GPT_PROMPT = "You are a helpful assistant."


def transform_markdown_with_gpt(markdown_text: str, prompt_type_or_custom: str = None) -> str:
    """
    Transforms the given Markdown text using OpenAI's GPT model.

    Args:
        markdown_text: The Markdown text to transform.
        prompt_type_or_custom: Either a key for a preset prompt (e.g., "table", "summary")
                               or a custom prompt string. If None, a default prompt is used.

    Returns:
        The transformed text from GPT.
        Returns an error message string starting with "⚠️ Error:" or "ℹ️ Info:" on failure or empty result.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return "⚠️ Error: OPENAI_API_KEY not configured. AI transformation cannot proceed."

    client = OpenAI(api_key=openai_api_key)

    if not markdown_text or not markdown_text.strip():
        logger.warning("Attempted GPT transformation with empty or whitespace-only Markdown.")
        return "⚠️ Error: Parsed markdown is empty. Please re-parse the document before running GPT transformation."

    prompt = PRESET_GPT_PROMPTS.get(prompt_type_or_custom, prompt_type_or_custom or DEFAULT_GPT_PROMPT)
    logger.debug(f"Using GPT prompt (first 100 chars): {prompt[:100]}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": markdown_text}
            ],
            temperature=0.1
        )
        result = response.choices[0].message.content.strip()

        if not result:
            logger.info("GPT transformation returned an empty result for prompt type/custom: {prompt_type_or_custom}")
            return "ℹ️ AI transformation returned an empty result. You might want to try a different prompt or check the input document."

        # As before, the encode-decode might be for specific character cleanup.
        # Retaining for now, but worth investigating if it's truly necessary or if direct string use is fine.
        cleaned_result = result.encode("utf-8", errors="replace").decode("utf-8")
        logger.debug(f"GPT transformation successful. Result length: {len(cleaned_result)}")
        return cleaned_result

    except openai.AuthenticationError as e:
        logger.error(f"OpenAI AuthenticationError during GPT transformation: {e}", exc_info=True)
        return "⚠️ Error: AI transformation failed due to an authentication issue with the OpenAI API. Please check your API key configuration."
    except openai.RateLimitError as e:
        logger.error(f"OpenAI RateLimitError during GPT transformation: {e}", exc_info=True)
        return "⚠️ Error: AI transformation failed because the API rate limit has been exceeded. Please try again later."
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI APIConnectionError during GPT transformation: {e}", exc_info=True)
        return "⚠️ Error: AI transformation failed due to a network issue connecting to the OpenAI API. Please check your internet connection."
    except openai.APIError as e: # Catch other specific OpenAI API errors
        logger.error(f"OpenAI APIError during GPT transformation: {e}", exc_info=True)
        return f"⚠️ Error: AI transformation failed due to an OpenAI API error. Details: {e}"
    except Exception as e:
        logger.error(f"Unexpected error during AI transformation: {e}", exc_info=True)
        return f"⚠️ Error: An unexpected error occurred during AI transformation. Details: {e}"
