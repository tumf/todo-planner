# Use a single stage for both building and running the application
FROM python:3.11-slim
WORKDIR /app

# Copy the project files
COPY poetry.lock pyproject.toml /app/

# Install poetry and dependencies
RUN pip install poetry && \
  poetry config virtualenvs.create false && \
  poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the application code
COPY . /app

# Command to run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]