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
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

RAG_AG_URL = os.getenv("RAG_AG_URL")
REP_AG_URL = os.getenv("REP_AG_URL")

app = FastAPI(
    title="Main Agent"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    async_conn = await aiosqlite.connect("checkpoints_agent.db")
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

When generating a report:
1) Call rag_ag.return_all_data() for full reports OR rag_ag.retrieve_data(query=...) for filtered reports.
2) Pass the returned string AS-IS to rep_ag.generate_excel_report(data=...).
Do NOT reformat, summarize, number, convert to JSON/CSV, or alter the text in any way.
If generate_excel_report fails, retry once with rag_ag.return_all_data() (AS-IS).

You must not ask any confirmation questions to the user, but instead make your best guess based on the query and proceed with the appropriate tool calls.
There are sample examples of conversations for your reference:

Scenario 1
User: Hi, how are you? I’d like to return something.
Assistant: Sure, please provide me with the details of the item and why you are returning it.
User: I want to return an Apple TV that was bought last week at Taipei 101 Apple Store. The Apple TV’s USB port is not working.
Assistant: Got it. Sorry to hear that. Can you also tell me how much you bought it for?
User: I bought it for 3000 NTD after a 10% discount.
Assistant: Got it. I have inserted a new item for refund: an Apple TV, purchased at Taipei 101 Apple Store at 3,300 NTD because the USB port is not working. Is there anything else I can help you with? Have a great day!

Scenario 2
User: Hi, how are you? I’d like to perform some data analysis on the items returned.
Assistant: Sure, what information would you like?
User: I’d like to know how many iPhones were returned in the past 2 weeks and whether the frequency has increased over the same timeframe.
Assistant: There has been a total of 13 iPhones returned in the past 2 weeks with a total loss of over 15,000 dollars. The frequency has been increasing lately due to screens having cracks out of the box. Maybe this is an issue we should address to reduce our losses.
User: Thanks for the insights. Please generate an Excel report for me to download that displays the information you mentioned.
Assistant: Sure, please click here to download your Excel report.
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


    