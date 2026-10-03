FROM python:3.13.15-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY product.tar.gz product.tar.gz.sha256 metadata.json requirements-staging.lock /srv/
RUN sha256sum -c product.tar.gz.sha256 \
    && mkdir -p /srv/releases/0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0 \
    && tar -xzf product.tar.gz -C /srv/releases/0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0 \
    && rm product.tar.gz product.tar.gz.sha256 \
    && python -m pip install --no-cache-dir --only-binary=:all: --no-deps --require-hashes \
        -r /srv/releases/0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0/requirements.lock \
        -r /srv/requirements-staging.lock
COPY runtime.py request_policy.py entrypoint.sh create-principals.py /srv/adapter/
RUN chmod 0555 /srv/adapter/entrypoint.sh
WORKDIR /srv/releases/0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0
USER 10001:10001
ENTRYPOINT ["/srv/adapter/entrypoint.sh"]
CMD ["gunicorn", "--chdir", "/srv/adapter", "--bind", "0.0.0.0:18743", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "--forwarded-allow-ips", "127.0.0.1", "runtime:staging_app"]
