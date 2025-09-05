FROM python:3.9-slim

WORKDIR /app

COPY app/ .

RUN pip install --no-cache-dir flask requests python-dotenv

CMD ["python", "app.py"]