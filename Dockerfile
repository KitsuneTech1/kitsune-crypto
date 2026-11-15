FROM python:3.12-slim

WORKDIR /app

# Install minimal build and networking tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY core/ /app/core/
COPY network/ /app/network/
COPY dashboard/ /app/dashboard/
COPY verifier/ /app/verifier/
COPY SPEC.md /app/SPEC.md

ENV PYTHONUNBUFFERED=1

EXPOSE 9200 8792

CMD ["python", "dashboard/server.py"]
