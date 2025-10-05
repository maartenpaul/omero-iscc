FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install zeroc-ice for Linux first
RUN pip install --no-cache-dir \
    https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl

# Install other dependencies
RUN pip install --no-cache-dir \
    iscc-sum>=0.1.0 \
    iscc-crypto>=0.3.0 \
    omero-py>=5.21.1 \
    requests>=2.31.0 \
    numpy>=1.24.0

COPY omero_iscc/ ./omero_iscc/

ENV OMERO_ISCC_HOST=omero-server
ENV OMERO_ISCC_USER=root
ENV OMERO_ISCC_PASSWORD=omero
ENV OMERO_ISCC_POLL_SECONDS=5
ENV OMERO_ISCC_PERSIST_DIR=/data

CMD ["python", "-m", "omero_iscc"]
