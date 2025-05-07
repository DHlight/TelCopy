# Use the official Python slim image as a base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    wget \
    apt-transport-https \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft Edge
RUN wget -q https://packages.microsoft.com/keys/microsoft.asc -O- | gpg --dearmor > microsoft.gpg \
    && install -o root -g root -m 644 microsoft.gpg /usr/share/keyrings/ \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update \
    && apt-get install -y microsoft-edge-stable \
    && rm -rf /var/lib/apt/lists/* microsoft.gpg

# Install pip requirements
COPY telegram_manager/requirements.txt /workspace/telegram_manager/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r telegram_manager/requirements.txt

# Copy the entire project
COPY . /workspace

# Expose port 8000 for the FastAPI app
EXPOSE 8000

# Default command to run the app with uvicorn
CMD ["uvicorn", "telegram_manager.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
