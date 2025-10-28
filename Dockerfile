# Use an official slim Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy pyproject.toml and README
COPY pyproject.toml README.md ./

# Copy source code before installing
COPY src ./src

# Install build backend first
RUN pip install --no-cache-dir uv_build

# Install the package (build wheel + dependencies)
RUN pip install --no-cache-dir .

# Set PYTHONPATH (optional, for clarity)
ENV PYTHONPATH=/app/src

EXPOSE 8000

# Run your MCP server
CMD ["python", "src/mcp_server/__init__.py"]
