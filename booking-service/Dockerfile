FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY booking-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY booking-service/ .
COPY proto /tmp/proto
COPY scripts/generate_proto.py /tmp/generate_proto.py
RUN python /tmp/generate_proto.py /tmp/proto /app
RUN chmod +x entrypoint.sh && useradd --create-home app && chown -R app:app migrations
USER app
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
