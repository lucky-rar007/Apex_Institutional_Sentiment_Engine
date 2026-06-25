# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency list first to leverage Docker build cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code files
COPY core/ core/
COPY dashboard/ dashboard/
COPY prompts/ prompts/
COPY registry/ registry/
COPY scraper/ scraper/
COPY storage/ storage/
COPY main.py .

# Expose port 8000
EXPOSE 8000

# Set default env variables (can be overridden at runtime)
ENV PORT=8000

# Start server
CMD ["python", "main.py"]
