# wc2026-predictor — container that ships with predictions pre-built.
FROM python:3.12-slim

# LightGBM needs libgomp at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY wc2026 ./wc2026
COPY data/seed ./data/seed
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[app,ml]"

# Build the store + model at image-build time (offline-safe; uses the committed seed if the
# network is unavailable during build). Comment out to build at first run instead.
RUN python -m wc2026.pipeline || python -m wc2026.pipeline --offline

EXPOSE 8501
ENV WC2026_LANG=es
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "wc2026/app/main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
