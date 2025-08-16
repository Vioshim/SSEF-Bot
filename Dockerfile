FROM python:3.13.7-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-interaction --no-ansi

COPY .env .env

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "main.py"]
