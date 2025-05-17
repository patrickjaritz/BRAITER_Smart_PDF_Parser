# 📄 Smart PDF Parser & Transformer

An interactive Streamlit app that allows you to upload a PDF, extract and analyze its content, detect tables/images/language, and optionally transform it using OpenAI GPT (e.g. into a summary, report, article, or structured CSV).

---

## 🚀 Features

- ✅ **Upload any PDF** and parse it using [LlamaParse](https://llamaindex.ai/)
- 🧠 **Detect content features**: language, tables, embedded images
- 📷 **Extract page images** and embedded images with gallery view
- 🤖 **Transform content** using GPT (OpenAI API)
  - Structure into tables (CSV)
  - Summarize or rewrite as a report/article
- 💾 **Download output** as:
  - Plain text (`.txt`)
  - Markdown (`.md`)
  - Word (`.docx`)
  - JSON (`.json`)
  - CSV (`.csv`, UTF-8 with BOM for Excel)
  - Excel (`.xlsx`)

---

## 🧰 Requirements

- Python 3.8+
- OpenAI account with API key
- LlamaParse API key

Install dependencies:

```bash
pip install -r requirements.txt
