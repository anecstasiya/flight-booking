FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY booking-service/requirements.txt booking-service/requirements.txt
COPY flight-service/requirements.txt flight-service/requirements.txt
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY proto /tmp/proto
COPY scripts/generate_proto.py /tmp/generate_proto.py
RUN python /tmp/generate_proto.py /tmp/proto /app
COPY tests tests
CMD ["python", "-m", "pytest", "-q", "tests"]
