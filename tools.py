"""VLM tools for chart, table, and image analysis — bound to a document."""
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import VLM_MODEL, CHART_ANALYSIS_PROMPT, TABLE_ANALYSIS_PROMPT, IMAGE_ANALYSIS_PROMPT
from models import ProcessedDocument


def create_tools_for_document(document: ProcessedDocument) -> list:
    vlm = ChatOpenAI(model=VLM_MODEL, temperature=0)

    def _call_vlm(image_base64: str, prompt: str) -> str:
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
        ])
        return vlm.invoke([msg]).content

    def _get_region(region_id: int, page_number: int):
        for page in document.pages:
            if page.page_number == page_number:
                return page.region_images.get(region_id)
        return None

    @tool
    def AnalyzeChart(region_id: int, page_number: int) -> str:
        """Analyze a chart or figure region using VLM to extract data points, axes, and trends.

        Args:
            region_id: The ID of the layout region (from the layout regions list).
            page_number: The page number where the region is located.
        """
        data = _get_region(region_id, page_number)
        if data is None:
            return f"Error: Region {region_id} on page {page_number} not found."
        return _call_vlm(data["base64"], CHART_ANALYSIS_PROMPT)

    @tool
    def AnalyzeTable(region_id: int, page_number: int) -> str:
        """Extract structured data from a table region using VLM.

        Args:
            region_id: The ID of the layout region (from the layout regions list).
            page_number: The page number where the region is located.
        """
        data = _get_region(region_id, page_number)
        if data is None:
            return f"Error: Region {region_id} on page {page_number} not found."
        return _call_vlm(data["base64"], TABLE_ANALYSIS_PROMPT)

    @tool
    def AnalyzeImage(region_id: int, page_number: int) -> str:
        """General visual analysis for figures, diagrams, or images that aren't charts or tables.

        Args:
            region_id: The ID of the layout region (from the layout regions list).
            page_number: The page number where the region is located.
        """
        data = _get_region(region_id, page_number)
        if data is None:
            return f"Error: Region {region_id} on page {page_number} not found."
        return _call_vlm(data["base64"], IMAGE_ANALYSIS_PROMPT)

    return [AnalyzeChart, AnalyzeTable, AnalyzeImage]
