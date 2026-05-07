FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements from the root (where we moved it)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual app code from the web_app directory into the container's root
COPY web_app/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
