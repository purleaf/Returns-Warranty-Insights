import os
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AnyMessage, HumanMessage
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI

load_dotenv()

RAG_AG_URL = os.getenv("RAG_AG_URL")
REP_AG_URL = os.getenv("REP_AG_URL")

app = FastAPI(
    title="Main Agent"
)


@tool
def get_current_time_in_taiwan() -> str:
    """Gets the current time in Taiwan time zone (Asia/Taipei, UTC+8)"""
    tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tz)
    return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

@app.post("/run_agent")
async def run_agent(model: str = "gpt-4.1-mini", user_query: str = "", session_id: str = "default_session") -> str:

    #Initializing client for our two mcp agents through SSE connection
    client = MultiServerMCPClient(
        {
            "rag_ag": {
                "url": f"{RAG_AG_URL}/sse",
                "transport": "sse"
            },
            "rep_ag": {
                "url": f"{REP_AG_URL}/sse",
                "transport": "sse"
            }
        }
    )
    #Now fetching two our MCP tools
    tools = await client.get_tools()
    tools.append(get_current_time_in_taiwan) #Adding the custom tool to get current time in Taiwan

    #Now initializing connection with db, that will be used to store checkpoints to keep conversation memory

    async_conn = await aiosqlite.connect("checkpoints_main_ag.db")
    checkpointer = AsyncSqliteSaver(async_conn)

    #Now initializing LLM model that will be used for our agent
    llm = ChatOpenAI(model=model)

    #Creating system message
    system_message = """
You are a coordinator agent for managing customer return orders and warranties. 
You have access to tools from 'rag_ag' for retrieving data or inserting new returns, 
and from 'rep_ag' for generating Excel reports based on retrieved data.
Use 'get_current_time_in_taiwan' for any time-related queries (e.g., filtering by recent dates in Taiwan time, which is UTC+8).

Delegate based on the user query:
- For retrieving returns (e.g., 'list defective headphones') or inserting new ones (e.g., 'add return for order 1101'), use rag_ag tools.
- For generating reports (e.g., 'create a report on all returns'), first retrieve the necessary data using rag_ag tools, then pass the retrieved data string directly to rep_ag's generate_excel_report tool.
- Always include relevant dates in Taiwan time if time-sensitive.
- Respond with the final result from the tools or a confirmation.

You must not ask any confirmation questions to the user, but instead make your best guess based on the query and proceed with the appropriate tool calls.
"""

    #Createing custom initial prompt for the agent
    system_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder("messages"),
        ]
    )

    #Now creating the agent itself with checkpointer and custom prompt
    agent_executor = create_react_agent(
        llm,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer
    )

    #Creating config to keep tracking of all the states in the ag conversation history with checkpointers
    config = RunnableConfig(configurable={"thread_id": session_id}, recursion_limit=70)

    #Formating the user input to match the checkpointer schema
    input_data = {"messages": [HumanMessage(content=user_query)]}

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


    