import os
from dotenv import load_dotenv

load_dotenv(override=True)

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Model Settings ---
AGENT_MODEL = "gpt-4o-mini"
VLM_MODEL = "gpt-4o-mini"
AGENT_TEMPERATURE = 0

# --- OCR Settings (image files only) ---
OCR_LANGUAGE = "en"
OCR_CONFIDENCE_THRESHOLD = 0.5

# --- Prompt Templates ---
CHART_ANALYSIS_PROMPT = """You are a Chart Analysis specialist.
Analyze this chart/figure image and extract:

1. **Chart Type**: (line, bar, scatter, pie, etc.)
2. **Title**: (if visible)
3. **Axes**: X-axis label, Y-axis label, and tick values
4. **Data Points**: Key values (peaks, troughs, endpoints)
5. **Trends**: Overall pattern description
6. **Legend**: (if present)

Return a JSON object with this structure:
```json
{
  "chart_type": "...",
  "title": "...",
  "x_axis": {"label": "...", "ticks": [...]},
  "y_axis": {"label": "...", "ticks": [...]},
  "key_data_points": [...],
  "trends": "...",
  "legend": [...]
}
```
"""

TABLE_ANALYSIS_PROMPT = """You are a Table Extraction specialist.
Extract structured data from this table image.

1. **Identify Structure**: Column headers, row labels, data cells
2. **Extract All Data**: Preserve exact values and alignment
3. **Handle Special Cases**: Merged cells, empty cells (mark as null), multi-line headers

Return a JSON object with this structure:
```json
{
  "table_title": "...",
  "column_headers": ["header1", "header2", ...],
  "rows": [
    {"row_label": "...", "values": [val1, val2, ...]},
    ...
  ],
  "notes": "any footnotes or source info"
}
```
"""

IMAGE_ANALYSIS_PROMPT = """You are a Visual Analysis specialist.
Analyze this image and describe:

1. **Content**: What does the image show?
2. **Key Elements**: Important visual elements, labels, annotations
3. **Context**: How does this relate to the document?

Provide a detailed but concise description.
"""

