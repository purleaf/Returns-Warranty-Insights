import os
import aiosqlite
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
import pandas
from datetime import datetime
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

mcp = FastMCP()


load_dotenv()

#Creating the agent tool to generate the report
@tool
async def generate_excel_report(data: str) -> str:
    """Generates an Excel report with Summary and Findings from the provided return orders data string."""
    try:
        # Parse the data string assuming format from retrieve_data: newline-separated key-value pairs, chunks are separated by \n\n)
        rows = []
        current_row = {}
        for chunk in data.split('\n\n'):
            for line in chunk.split('\n'):
                if line.strip() and ': ' in line:
                    key, value = line.split(': ', 1)
                    current_row[key.strip()] = value.strip()
            if current_row:
                rows.append(current_row)
                current_row = {}
        if current_row:
            rows.append(current_row)

        if not rows:
            return "Error: No valid data provided to generate report."

        dataFrame = pandas.DataFrame(rows)
        # Ensure numeric columns
        if 'cost' in dataFrame.columns:
            dataFrame['cost'] = pandas.to_numeric(dataFrame['cost'], errors='coerce')

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
        llm = ChatOpenAI(model="gpt-4.1-mini")
        findings_prompt = (
            "Analyze the following summary of customer return orders and generate 5-10 key findings or insights. "
            "Focus on trends, common issues, potential business impacts, and recommendations. "
            f"Summary: {summary}"
        )
        findings_response = await llm.ainvoke(findings_prompt)
        findings = findings_response.content

        #Creating the excel file containing three sheets Raw Data, Summary and Findings
        file_path = f"return_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with pandas.ExcelWriter(file_path, engine='openpyxl') as writer:
            dataFrame.to_excel(writer, sheet_name='Raw Data', index=False)
            pandas.DataFrame.from_dict(summary, orient='index', columns=['Value']).to_excel(writer, sheet_name='Summary')
            pandas.DataFrame({"Findings": findings.split('\n')}).to_excel(writer, sheet_name='Findings', index=False)

        return f"Excel report generated successfully at {file_path}"
    except Exception as e:
        return f"Error generating report: {str(e)}"

@mcp.tool(description="Generates an Excel report with Summary and Findings from the provided return orders data string.")
async def run_rep_ag(query: str, session_id: str = "default_session") -> str:

    #Now initializing connection with db, that will be used to store checkpoints to keep conversation memory

    async_conn = await aiosqlite.connect("checkpoints_rep_ag.db")
    checkpointer = AsyncSqliteSaver(async_conn)

    #Now initializing LLM model that will be used for our agent
    llm = ChatOpenAI(model="gpt-4.1")

    system_message = """
    You are a report generation agent for customer return orders. Analyze the provided data in the user query and use the 'generate_excel_report' tool to create an Excel report with Summary and Findings. Extract the data from the query and pass it directly to the tool.
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

@app.get("/ping")
async def ping():
    return {
        "status": "ok",
    }

app.mount("/", mcp.sse_app())