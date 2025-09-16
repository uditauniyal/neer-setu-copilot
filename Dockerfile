FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x docker_entrypoint.sh
EXPOSE 8000 8501
ENTRYPOINT ["./docker_entrypoint.sh"]
