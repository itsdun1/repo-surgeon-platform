# surgeon-service — FastAPI dispatcher
#
# Runs:
#   - the webhook receiver + worker
#   - the gitagent CLI as a subprocess (must be in this container)
#   - git clone of target repos (must have git, gh, npm, python tooling so the
#     agent can run tests in cloned workspaces)
#
# Multi-stage: keep image lean by separating build/install from runtime.

FROM node:20-bookworm-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Core OS deps: python (for our hook scripts + custom tools), git, gh CLI,
# build essentials (for some Python wheels), curl/ca-certs for HTTPS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        git curl ca-certificates gnupg \
        build-essential \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir uv

# Install gitagent CLI globally (Lyzr's GAP runtime)
RUN npm install -g --no-audit --no-fund @open-gitagent/gitagent

WORKDIR /app/surgeon-service

# Copy full source first so editable install has the package available
COPY surgeon-service/ /app/surgeon-service/

# Create venv and install dependencies + the package itself
RUN uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install -e .
ENV PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV=/opt/venv

# Note: repo-surgeon/ is bind-mounted at runtime (not COPY'd) so memory commits
# from the host's clone persist. See docker-compose.yml.

EXPOSE 18000

# Entrypoint runs alembic migrations then uvicorn.
COPY surgeon-service/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

CMD ["/usr/local/bin/docker-entrypoint.sh"]
