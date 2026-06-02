FROM python:3.11-slim
#FROM mirror-docker.runflare.com/library/python:3.11-slim


WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

#RUN pip install --no-cache-dir -r requirements.txt
#RUN pip install -i https://package-mirror.liara.ir/repository/pypi/simple --no-cache-dir -r requirements.txt
#RUN pip install -i https://mirror-pypi.runflare.com/simple --no-cache-dir -r requirements.txt
#RUN pip install -i https://mirror.abrha.net/repository/pypi/simple --no-cache-dir -r requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel && \
    (pip install --no-cache-dir -r requirements.txt || \
     pip install --no-cache-dir -i https://package-mirror.liara.ir/repository/pypi/simple -r requirements.txt || \
     pip install --no-cache-dir -i https://mirror-pypi.runflare.com/simple -r requirements.txt || \
     pip install --no-cache-dir -i https://mirror.abrha.net/repository/pypi/simple -r requirements.txt)


COPY . .

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]