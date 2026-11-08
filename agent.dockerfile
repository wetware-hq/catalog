# syntax=docker/dockerfile:1.7
FROM rust:1.85.0-bookworm AS build

WORKDIR /workspace
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY sql ./sql
RUN cargo build --locked --release --bin catalog-agent

FROM gcr.io/distroless/cc-debian12:nonroot

LABEL org.opencontainers.image.source="https://github.com/wetware-hq/catalog"
LABEL org.opencontainers.image.title="catalog-agent"

COPY --from=build /workspace/target/release/catalog-agent /usr/local/bin/catalog-agent

USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/catalog-agent"]
CMD ["serve"]
