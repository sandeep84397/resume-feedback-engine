FROM python:3.12-slim

# Non-root user
RUN useradd --create-home --uid 10001 rfe
WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . uvicorn

# Drop privileges
USER rfe

EXPOSE 8000
CMD ["uvicorn", "rfe.main:app", "--host", "0.0.0.0", "--port", "8000"]
