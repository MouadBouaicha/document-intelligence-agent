"""LangGraph agent — text passed directly in system prompt (like the notebook)."""
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from config import AGENT_MODEL, AGENT_TEMPERATURE
from models import ProcessedDocument
from tools import create_tools_for_document


# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a Document Intelligence Agent.
You analyze documents by combining OCR text with visual analysis tools.

## Document Info
- **Source**: {source_name}
- **Pages**: {page_count}

## Document Text (in reading order)
{ordered_text}

## Document Layout Regions
{layout_regions}

## Your Tools
- **AnalyzeChart(region_id, page_number)**: Analyze a chart or figure region using VLM. Use for charts, graphs, figures.
- **AnalyzeTable(region_id, page_number)**: Extract structured table data using VLM.
- **AnalyzeImage(region_id, page_number)**: General visual analysis for other images or diagrams.

## Instructions
1. For TEXT questions: Answer directly from the OCR text above — it is already extracted and ordered.
2. For TABLE questions: Use AnalyzeTable with the correct region_id and page_number.
3. For CHART/FIGURE questions: Use AnalyzeChart with the correct region_id and page_number.
4. Always cite the page number when referencing content.
"""


def _format_ordered_text(doc: ProcessedDocument) -> str:
    lines = []
    for page in doc.pages:
        if doc.page_count > 1:
            lines.append(f"\n### Page {page.page_number}")
        for item in page.ordered_text:
            lines.append(f"[{item['position']}] {item['text']}")
    return "\n".join(lines) or "(no text extracted)"


def _format_layout_regions(doc: ProcessedDocument) -> str:
    lines = []
    for page in doc.pages:
        for region in page.layout_regions:
            page_info = f", page {page.page_number}" if doc.page_count > 1 else ""
            lines.append(
                f"  - Region {region.region_id}{page_info}: "
                f"{region.region_type} (confidence: {region.confidence:.2f})"
            )
    return "\n".join(lines) or "(no regions detected)"


# ── Agent factory ────────────────────────────────────────────────────────────

def create_agent(document: ProcessedDocument):
    tools = create_tools_for_document(document)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        source_name=document.source_name,
        page_count=document.page_count,
        ordered_text=_format_ordered_text(document),
        layout_regions=_format_layout_regions(document),
    )

    llm = ChatOpenAI(model=AGENT_MODEL, temperature=AGENT_TEMPERATURE)
    memory = MemorySaver()
    agent = create_react_agent(llm, tools, prompt=system_prompt, checkpointer=memory)
    return agent


# ── Streaming ────────────────────────────────────────────────────────────────

def stream_agent(agent, question: str, session_id: str = "default"):
    """Stream agent execution, yielding tool_call, tool_result, and answer events."""
    config = {"configurable": {"thread_id": session_id}}

    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in chunk.items():
            for msg in node_output.get("messages", []):
                if node_name == "agent":
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            yield {"type": "tool_call", "data": {"name": tc["name"], "args": tc["args"]}}
                    elif hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
                        yield {"type": "answer", "data": {"content": msg.content}}
                elif node_name == "tools":
                    if hasattr(msg, "name") and hasattr(msg, "content"):
                        yield {"type": "tool_result", "data": {"name": msg.name, "result": str(msg.content)}}
