FROM python:3.10-slim

WORKDIR /app

# ndnc は PyPI から取得（独立した外部パッケージとして扱う）
COPY seed/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# seed/ だけをコピー（ndn-compiler のソースは不要）
COPY seed/ ./seed/

# seed パッケージを import できるようにする
ENV PYTHONPATH=/app

CMD ["python3", "-m", "seed.main", "/seed"]
