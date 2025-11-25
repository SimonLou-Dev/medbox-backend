FROM mcr.microsoft.com/devcontainers/base:ubuntu24.04

# Installer Python 3.11 + dépendances
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installer Poetry
ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:${PATH}"
RUN curl -sSL https://install.python-poetry.org | python3.11 -

# Créer un utilisateur non-root (devcontainers aiment bien "vscode")
RUN useradd -m vscode
USER vscode

WORKDIR /workspace

CMD ["bash"]
