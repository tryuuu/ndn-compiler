FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y make time && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install .
# seed/ はリポジトリルートの独立したパッケージのため PYTHONPATH で参照できるようにする
ENV PYTHONPATH=/app
CMD ["ndnc", "--help"]