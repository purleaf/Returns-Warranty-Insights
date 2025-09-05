import os
import sqlite3
import aiosqlite
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
from langchain.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from pydantic import BaseModel, Field
from langchain.schema import Document
import pandas
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

mcp = FastMCP()


load_dotenv()

#Creating a model for parsging the data from CSV
class ReturnOrder(BaseModel):
    order_id: str = Field(...)
    product: str = Field(...)
    category: str = Field(...)
    return_reason: str = Field(...)
    cost: float = Field(...)
    approved_flag: str = Field(...)
    store_name: str = Field(...)
    date: str = Field(...)

#First loading our CSV file
loader = CSVLoader(file_path="sample.csv", csv_args={'delimiter': ','})
documents = loader.load()

#Next we need to process the file in order to store it in the vectore db 
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100) #Creating the text splitter and setting the chunk size and overlap to make sure we do not loose any context
chunks = text_splitter.split_documents(documents)#First we are splitting it into chunks
embeddings = OpenAIEmbeddings() #I've chosen openai embedding model due to its good performance
vectorstore = Chroma.from_documents(chunks, embeddings) #Now we are creating the vectore store and upload the processed chunks into it




async def setup_db():
    #Creating connection with the sqlite db
    async with aiosqlite.connect("customer-data.db") as conn:
        cursor = await conn.cursor()

        #Now creating the table to store the data from the CSV you provided me with
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS return_orders (
            order_id TEXT PRIMARY KEY,
            product TEXT,
            category TEXT,
            return_reason TEXT,
            cost REAL,
            approved_flag TEXT,
            store_name TEXT,
            date TEXT
            )
            ''')
        await conn.commit()
        #Now loading our CSV file and inserting the data into the table, by converting it into list of tuples, where a tuple corresponds to a row in the table
        dataFrame = pandas.read_csv("sample.csv") 
        data = dataFrame.to_records(index=False).tolist()
        await cursor.executemany('''
            INSERT OR REPLACE INTO return_orders (order_id, product, category, return_reason, cost, approved_flag, store_name, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
        await conn.commit()

#Creating the agent tool to retrieve from the vectore store
@tool
async def retrieve_data(query: str, k_n: int = 10) -> str:
    """Returning the relevant data from the vectore store"""
    retriever = vectorstore.as_retriever(search_kwargs={"k": k_n}) 
    chunks = await retriever.ainvoke(query)
    return "\n\n".join([doc.page_content for doc in chunks])

#Creating the agent tool to retrieve all the data from the db
@tool
async def return_all_data() -> str:
    """Returning all the data from the database"""
    async with aiosqlite.connect("customer-data.db") as conn:
        cursor = await conn.cursor()
        cursor = await conn.execute("SELECT * FROM return_orders")    
        rows = await cursor.fetchall()
        if not rows:
            return "No return orders found."

        blocks = []
        for row in rows:
            blocks.append("\n".join([
                f"order_id: {row[0]}",
                f"product: {row[1]}",
                f"category: {row[2]}",
                f"return_reason: {row[3]}",
                f"cost: {row[4]}",
                f"approved_flag: {row[5]}",
                f"store_name: {row[6]}",
                f"date: {row[7]}",
            ]))
        return "\n\n".join(blocks)

#Creating the agent tool to insert new return order into the db
@tool
async def insert_return(order_id: str, product: str, category: str, return_reason: str, cost: float, approved_flag: str, store_name: str, date: str) -> str:
    """Inserting a new return order into the database and returning the current list of return orders"""
    async with aiosqlite.connect("customer-data.db") as conn:
        try:
            cursor = await conn.cursor()
            await cursor.execute('''
                INSERT INTO return_orders (order_id, product, category, return_reason, cost, approved_flag, store_name, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (order_id, product, category, return_reason, cost, approved_flag, store_name, date))
            await conn.commit()

            #Now uploading the new data into the vectore store as well
            new_chunks = "\n".join([
                f"order_id: {order_id}",
                f"product: {product}",
                f"category: {category}",
                f"return_reason: {return_reason}",
                f"cost: {cost}",
                f"approved_flag: {approved_flag}",
                f"store_name: {store_name}",
                f"date: {date}"
            ])
            new_doc = Document(page_content=new_chunks)
            await vectorstore.aadd_documents([new_doc])

            #And for the output we return the current list of return orders
            cursor = await conn.execute("SELECT order_id, product, store_name, date FROM return_orders")    
            rows = await cursor.fetchall()
            result = "\n".join([f"Order ID: {row[0]}, Product: {row[1]}, Store: {row[2]}, Date: {row[3]}" for row in rows])
            return f"Return order inserted successfully. Current return orders:\n{result}"
        except Exception as e:
            return f"Error inserting data: {str(e)}"


@mcp.tool(description="Retrieves and writes data from the vector store based on the provided query.")
async def run_rag_ag(query: str = "", session_id: str = "default_session") -> str:

    await setup_db() #First we are setting up the db with our data before running the agent

    #Now initializing connection with db, that will be used to store checkpoints to keep conversation memory

    async_conn = await aiosqlite.connect("checkpoints_agent.db")
    checkpointer = AsyncSqliteSaver(async_conn)

    #Now initializing LLM model that will be used for our agent
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

    system_message = """
    You are a retrieval agent for managing customer return orders. 
    Use the 'retrieve_data' tool for queries and 'insert_return' tool for insertions from natural language prompts. 
    After insertion, it's extremely important to output the current list of returned orders you will be rewarded for returning the full list. 
    Prohibited behavior includes vague responses, incomplete lists, or failure to acknowledge the inserted data. 
    Example of prohibited output: 
    '- ... (and many more, up to Order ID: 1100, Product: Tablet, Store: Sunnyvale Town, Date: 2025-01-03)'

    """
    #Configuring the system prompt for our agent
    system_prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    MessagesPlaceholder(variable_name="messages"),
    ])

    #Now creating the agent itself with checkpointer and custom prompt
    agent_executor = create_react_agent(
        llm,
        tools=[retrieve_data, insert_return, return_all_data], #here we are passing the retriever as a tool to our agent
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
    title="RAG Agent"
)

@app.get("/ping")
async def ping():
    return {
        "status": "ok",
    }

app.mount("/", mcp.sse_app())