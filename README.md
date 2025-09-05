## Live Demo
Test the agent: 
https://ui-28829503485.asia-east1.run.app/  (deployed with Google Cloud)

Before start: 
- Click on the settings button in the top right corner to set
    - Model (`gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`)
    - Session name

## Test Locally
### 1. Set env file
```
OPENAI_API_KEY=xxxx
RAG_AG_URL=http://rag-ag:8001
REP_AG_URL=http://rag-ag:8002
MAIN_AG_URL=http://main-ag:8000
PORT=8080 #Port for UI to run
```

### 2. Compose the container
```
docker compose up -d
```
