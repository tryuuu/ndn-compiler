FROM python:3.10-slim

WORKDIR /app

# python-ndn は PyPI から取得
COPY seed/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# ndnc はローカルソースからインストール（最新の変更を反映するため）
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install .

# seed/ をコピー
COPY seed/ ./seed/

# seed パッケージを import できるようにする
ENV PYTHONPATH=/app

CMD ["python3", "-m", "seed.main", "/seed"]
