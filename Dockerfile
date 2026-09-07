FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY load_balancer ./load_balancer
COPY examples ./examples
RUN pip install --no-cache-dir .
COPY config.docker.json ./config.json

EXPOSE 8080
CMD ["python", "-m", "load_balancer", "--config", "config.json"]
