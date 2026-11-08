# syntax=docker/dockerfile:1.7
FROM rust:1.85.0-bookworm AS build

WORKDIR /workspace
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY sql ./sql
RUN cargo build --locked --release --bin catalog-tracer

FROM debian:bookworm-slim

ARG KUBECTL_VERSION=v1.31.2
ARG KUBECTL_SHA256=399e9d1995da80b64d2ef3606c1a239018660d8b35209fba3f7b0bc11c631c68

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && echo "${KUBECTL_SHA256}  /usr/local/bin/kubectl" | sha256sum -c - \
    && chmod 755 /usr/local/bin/kubectl \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 65532 --user-group --no-create-home --shell /usr/sbin/nologin catalog

LABEL org.opencontainers.image.source="https://github.com/wetware-hq/catalog"
LABEL org.opencontainers.image.title="catalog-tracer"

COPY --from=build /workspace/target/release/catalog-tracer /usr/local/bin/catalog-tracer

USER catalog
ENTRYPOINT ["/usr/local/bin/catalog-tracer"]
