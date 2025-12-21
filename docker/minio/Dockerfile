FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y wget ca-certificates curl \
    && wget https://dl.min.io/client/mc/release/linux-arm64/mc -O /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc \
    && update-ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY init.sh /minio/init.sh
RUN chmod +x /minio/init.sh
ENTRYPOINT ["/bin/sh", "/minio/init.sh"]