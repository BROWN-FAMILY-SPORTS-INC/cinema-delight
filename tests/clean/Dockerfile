# A clean clone on a bare machine: only what the README says is needed, then every check.
#   tests/clean/run.sh
FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium ffmpeg python3 git ca-certificates fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
RUN useradd -m maker && mkdir /work && chown maker /work
USER maker
WORKDIR /work
COPY --chown=maker:maker . .
RUN git init -q && git add -A && git -c user.name=test -c user.email=test@example.invalid commit -qm clean
ENV CINEMA_MIN_FREE_BYTES=1073741824
CMD ["tests/run.sh"]
