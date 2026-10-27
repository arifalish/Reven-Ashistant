FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# Copy application files
COPY app/ app/
COPY core/ core/
COPY interfaces/ interfaces/
COPY middleware/ middleware/
COPY workers/ workers/
COPY scripts/ scripts/
COPY skills/ skills/

# Bootstrap the 15 skill instruction packages at image build time.
RUN chmod +x scripts/bootstrap_skills.sh && ./scripts/bootstrap_skills.sh

EXPOSE 8000

# Configure Telegram's webhook from RENDER_EXTERNAL_URL, then start the API.
CMD ["python", "scripts/start.py"]
