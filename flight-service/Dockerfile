FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY flight-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY flight-service/ .
COPY proto /tmp/proto
COPY scripts/generate_proto.py /tmp/generate_proto.py
RUN python /tmp/generate_proto.py /tmp/proto /app
RUN chmod +x entrypoint.sh && useradd --create-home app && chown -R app:app migrations
USER app
EXPOSE 50051
ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "app.main"]
