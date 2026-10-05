# VAYU-READY API / worker image. Build context = repository root.
# Everything is installed at build time; nothing is downloaded at runtime.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MPLCONFIGDIR=/tmp/mpl
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
# CPU-only PyTorch keeps the image small; the rest comes from PyPI.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt

COPY backend/ /app/
COPY ml/ /app/ml/
# Trained models and results ship inside the image (docker-compose mounts ./models over them)
COPY models/ /app/models/
COPY results/ /app/results/
COPY pytest.ini /app/pytest.ini
RUN sed -i 's/^pythonpath = .*/pythonpath = ./; s#^testpaths = .*#testpaths = tests#' /app/pytest.ini

RUN useradd --create-home --uid 10001 vayu && mkdir -p /app/models /app/results /app/data && chown -R vayu /app
USER vayu

ENV MODEL_DIR=/app/models RESULTS_DIR=/app/results DATA_DIR=/app/data
EXPOSE 8000
# Hosting platforms such as Render set $PORT; locally it is 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
