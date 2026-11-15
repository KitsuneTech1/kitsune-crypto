# Kitsune Private Layer (KPL) - Local Devnet Node
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Kitsune Private Layer Validator Node"
LABEL org.opencontainers.image.description="Compile-time verified privacy-preserving Layer-1 BFT validator"
LABEL org.opencontainers.image.source="https://github.com/KitsuneTech1/kitsune-crypto"

WORKDIR /opt/kpl

# Copy core engine, networking, and verification modules
COPY core/ /opt/kpl/core/
COPY network/ /opt/kpl/network/
COPY verifier/ /opt/kpl/verifier/
COPY dashboard/ /opt/kpl/dashboard/

ENV PYTHONPATH="/opt/kpl"
ENV PYTHONUNBUFFERED=1

EXPOSE 9200

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9200/status', timeout=2)" || exit 1

ENTRYPOINT ["python3", "-m", "network.daemon"]
