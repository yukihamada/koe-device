FROM rust:1.88-bookworm AS chef
RUN cargo install cargo-chef
WORKDIR /app

FROM chef AS planner
COPY server/ server/
WORKDIR /app/server
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /app/server/recipe.json server/recipe.json
WORKDIR /app/server
RUN cargo chef cook --release --recipe-path recipe.json
COPY server/ .
RUN cargo build --release --bin koe-server

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/server/target/release/koe-server /usr/local/bin/koe-server
COPY docs/ /app/docs/
ENV STATIC_DIR=/app/docs PORT=8080
EXPOSE 8080
CMD ["koe-server"]
