# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Set the working directory to /app
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install tzdata for timezone configuration
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

# Set the timezone
ENV TZ=Asia/Kathmandu
ENV UV_PYTHON_PREFERENCE=only-system

# Copy the lockfile and pyproject.toml
# This allows caching the dependency installation step
COPY uv.lock pyproject.toml /app/

# Install the project's dependencies using the lockfile and settings
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the source code into the image
COPY . /app/

# Place the virtualenv in the path so we can use `python` directly
ENV PATH="/app/.venv/bin:$PATH"

# Run the application
# Run the application
CMD ["python", "main.py"]
