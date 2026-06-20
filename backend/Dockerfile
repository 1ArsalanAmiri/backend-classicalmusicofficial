FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources || true && \
    apt-get update && \
    apt-get install -y unrar libarchive-tools && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    (pip install --no-cache-dir -r requirements.txt || \
     pip install --no-cache-dir -i https://package-mirror.liara.ir/repository/pypi/simple -r requirements.txt || \
     pip install --no-cache-dir -i https://mirror-pypi.runflare.com/simple -r requirements.txt || \
     pip install --no-cache-dir -i https://mirror.abrha.net/repository/pypi/simple -r requirements.txt)

COPY . .

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
