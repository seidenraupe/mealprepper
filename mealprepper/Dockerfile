ARG BUILD_ARCH=amd64
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base-python:3.13-alpine3.24

ARG BUILD_ARCH
ARG CLOUDFLARED_VERSION=2026.10.3

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    MEALPREPPER_WWW_DIR=/app/www

WORKDIR /app

RUN apk add --no-cache bash tzdata \
 && pip3 install flask==3.1.1 waitress==3.0.2

# cloudflared spricht Cloudflare nur ausgehend an — kein eingehender Port nötig.
RUN set -e; \
    case "${BUILD_ARCH}" in \
      amd64) CF_ARCH=amd64; CF_SHA=053b80b0a23031a038fdbf3c073f59f82b8f1f152aa67971d7383ffafc0dbab0 ;; \
      aarch64) CF_ARCH=arm64; CF_SHA=89297ebfb9e8c99c0dc013a1140601453cf3798d8306c5591651f4a3f5210be8 ;; \
      *) echo "Nicht unterstützte Architektur: ${BUILD_ARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /usr/local/bin/cloudflared \
      "https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-${CF_ARCH}"; \
    echo "${CF_SHA}  /usr/local/bin/cloudflared" | sha256sum -c -; \
    chmod +x /usr/local/bin/cloudflared; \
    cloudflared --version

COPY main.py db.py season.py /app/
COPY www /app/www
COPY run.sh /run.sh
RUN sed -i 's/\r$//' /run.sh && chmod a+x /run.sh

LABEL \
  io.hass.name="Mealprepper" \
  io.hass.description="Manuelle Menüplanung über Cloudflare Tunnel" \
  io.hass.version="0.1.0" \
  io.hass.type="addon" \
  io.hass.arch="amd64|aarch64"

# s6-Entrypoint umgehen: nur API + optionaler Tunnel.
ENTRYPOINT ["/bin/bash"]
CMD ["/run.sh"]
