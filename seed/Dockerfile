FROM python:3.10-slim

WORKDIR /app

COPY seed/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt ndnc

# seed/ をコピー
COPY seed/ ./seed/

# seed パッケージを import できるようにする
ENV PYTHONPATH=/app

CMD ["python3", "-m", "seed.main", "/seed"]
