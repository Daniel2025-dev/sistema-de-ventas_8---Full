FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLET_HOST=0.0.0.0 FLET_PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "flet run --web --host ${FLET_HOST} --port ${PORT:-${FLET_PORT}} index.py"]
