import os
import aiosqlite
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_openai import ChatOpenAI
from typing import Any, Dict, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
import pandas
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from mcp.server.fastmcp import FastMCP
from fastapi.staticfiles import StaticFiles
import uuid
from pathlib import Path
import re

mcp = FastMCP()

load_dotenv()

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./reports")).resolve()
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

#Here i created a function to coerce the OpenAI message content into the plain text
def _to_text(content: Any) -> str:
    """Coerce LC message content (str | list[dict|str] | other) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item and isinstance(item["text"], str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)

#This is a function to normalize the keys from the user input to match our model fields
def _norm_key(k: str) -> str:
    k = k.strip()
    # common mappings to snake_case
    k = k.lower()
    k = k.replace(" ", "_")
    k = k.replace("-", "_")
    # specific synonyms
    mapping = {
        "order_id": "order_id",
        "product": "product",
        "category": "category",
        "return_reason": "return_reason",
        "reason": "return_reason",
        "cost": "cost",
        "price": "cost",
        "approved": "approved_flag",
        "approved_flag": "approved_flag",
        "store": "store_name",
        "store_name": "store_name",
        "date": "date",
    }
    return mapping.get(k, k)

#One more function for a record parsing from the user input
def _parse_records(data: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []

    #If we see ", " and multiple ":" in a single line it treats treat as format B
    lines = [ln for ln in data.splitlines() if ln.strip()]
    looks_like_b = any(ln.count(":") >= 2 and ", " in ln for ln in lines)

    if looks_like_b:
        for ln in lines:
            row: Dict[str, str] = {}
            for part in ln.split(","):
                if ":" in part:
                    k, v = part.split(":", 1)
                    row[_norm_key(k)] = v.strip()
            if row:
                records.append(row)
    else:
        # format A
        chunks = re.split(r"\n\s*\n", data.strip())
        for chunk in chunks:
            row: Dict[str, str] = {}
            for ln in chunk.splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    row[_norm_key(k)] = v.strip()
            if row:
                records.append(row)

    return records


#Creating the agent tool to generate the report
@tool
async def generate_excel_report(data: str) -> str:
    """Generates an Excel report with Summary and Findings from the provided return orders data string."""
    try:
        # Parse the data string assuming format from retrieve_data: newline-separated key-value pairs, chunks are separated by \n\n)
        raw = data if isinstance(data, str) else _to_text(data)
        rows = _parse_records(raw)

        if not rows:
            return "Error: No valid data provided to generate report."

        dataFrame = pandas.DataFrame(rows)
        # Ensure numeric columns
        if 'cost' in dataFrame.columns:
            dataFrame['cost'] = pandas.to_numeric(dataFrame['cost'], errors='coerce')
        for col in ("approved_flag", "product", "category", "return_reason", "store_name"):
            if col in dataFrame.columns:
                dataFrame[col] = dataFrame[col].astype(str)
            
        #Formating the summary of all the data in the dataframe
        summary = {
            'Total Returns': len(dataFrame),
            'Total Cost': dataFrame['cost'].sum() if 'cost' in dataFrame.columns else 0.0,
            'Average Cost': dataFrame['cost'].mean() if 'cost' in dataFrame.columns else 0.0,
            'By Category': dataFrame['category'].value_counts().to_dict() if 'category' in dataFrame.columns else {},
            'By Return Reason': dataFrame['return_reason'].value_counts().to_dict() if 'return_reason' in dataFrame.columns else {},
            'By Store': dataFrame['store_name'].value_counts().to_dict() if 'store_name' in dataFrame.columns else {},
            'Approved Count': dataFrame['approved_flag'].value_counts().get('Yes', 0) if 'approved_flag' in dataFrame.columns else 0,
        }

        #Now I use LLM to generate findings based on the summary provided
        llm = ChatOpenAI(model="gpt-5-mini", reasoning={"effort": "minimal"})
        findings_prompt = (
            "Analyze the following summary of customer return orders and generate 5-10 key findings or insights. "
            "Focus on trends, common issues, potential business impacts, and recommendations. "
            f"Summary: {summary}"
        )
        findings_response = await llm.ainvoke(findings_prompt)
        findings_text = _to_text(findings_response.content)
        findings_lines = [ln.strip() for ln in findings_text.splitlines() if ln.strip()]
        # findings = findings_response.content


        #Creating the excel file containing three sheets Raw Data, Summary and Findings
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stem = f"return_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        filename = f"{stem}.xlsx"
        file_path = REPORTS_DIR / filename
        with pandas.ExcelWriter(file_path, engine='openpyxl') as writer:
            dataFrame.to_excel(writer, sheet_name='Raw Data', index=False)
            pandas.DataFrame.from_dict(summary, orient='index', columns=['Value']).to_excel(writer, sheet_name='Summary')
            pandas.DataFrame({"Findings": findings_lines}).to_excel(writer, sheet_name='Findings', index=False)
        
        url_files = f"{PUBLIC_BASE_URL}/files/{filename}"
        url_download = f"{PUBLIC_BASE_URL}/download/{filename}"

        return (
            f"Excel report generated.\n\n"
            f"- Direct link: {url_files}\n"
            f"- Force download: {url_download}\n"
        )

        return f"Excel report generated successfully at {file_path}"
    except Exception as e:
        return f"Error generating report: {str(e)}"

@mcp.tool(description="Generates an Excel report with Summary and Findings from the provided return orders data string.")
async def run_rep_ag(query: str, session_id: str = "default_session") -> str:

    #Now initializing connection with db, that will be used to store checkpoints to keep conversation memory

    async_conn = await aiosqlite.connect("checkpoints_agent.db")
    checkpointer = AsyncSqliteSaver(async_conn)

    #Now initializing LLM model that will be used for our agent
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.1)

    system_message = """
    You are a report generation agent for customer return orders. 
    Analyze the provided data in the user query and use the 'generate_excel_report' tool to create an Excel report with Summary and Findings. 
    Extract the data from the query and pass it directly to the tool.
    """

    #Configuring the system prompt for our agent
    system_prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    MessagesPlaceholder(variable_name="messages"),
    ])

    #Now creating the agent itself with checkpointer and custom prompt
    agent_executor = create_react_agent(
        llm,
        tools=[generate_excel_report],
        prompt=system_prompt,
        checkpointer=checkpointer
    )

    #Creating config to keep tracking of all the states in the ag conversation history with checkpointers
    config = RunnableConfig(configurable={"thread_id": session_id}, recursion_limit=70)

    input_data = {"messages": [HumanMessage(content=query)]}

    #Now invoking the agent
    async for chunk in agent_executor.astream(input_data, config=config):
        print(chunk)
    print("Agent execution completed")

    #And finally retrieve the final state from the checkpointer to extract the agent's output
    checkpoint = await checkpointer.aget(config)
    final_output_text = ""
    if checkpoint:
        state = checkpoint["channel_values"]
        messages = state.get("messages", [])
        for message in reversed(messages):
            if getattr(message, "type", "") == "ai" and not getattr(message, "tool_calls", []): #Ensuring we get the final agent message, but not a tool call
                raw_content = getattr(message, "content", "")
                final_output_text = raw_content
                break
    else:
        print("No checkpoint found for final state")

    return final_output_text if final_output_text else "No output generated"

app = FastAPI(
    title="Report Agent"
)

@app.get("/download/{filename}") #Endpoint to download the generated by the agnet report
async def download_file(filename: str):
    fullpath = REPORTS_DIR / filename
    if not fullpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(fullpath),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/ping")
async def ping():
    return {
        "status": "ok",
    }

app.mount("/", mcp.sse_app()) #mounting mcp app 

app.mount("/files", StaticFiles(directory=str(REPORTS_DIR), html=False), name="files")


app.add_middleware( #adding allowence for url clicking in browser
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)