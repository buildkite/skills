# Sandbox container for the Ralph Wiggum conversion agent.
# The agent has full access inside this container but can't escape --
# all file system changes, tool installs, and network calls are
# confined to this disposable Docker environment.

FROM node:20-slim

# Install useful system tools
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    curl \
    jq \
    ca-certificates \
    gnupg \
  && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Pre-install Buildkite agent so the agent doesn't waste budget installing it
RUN curl -sL https://raw.githubusercontent.com/buildkite/agent/main/install.sh | bash

# Pre-install Buildkite CLI (bk) via .deb package
RUN BK_VERSION=$(curl -sL "https://api.github.com/repos/buildkite/cli/releases/latest" | grep '"tag_name"' | sed 's/.*"v\(.*\)".*/\1/') && \
    ARCH=$(dpkg --print-architecture) && \
    curl -sL "https://github.com/buildkite/cli/releases/download/v${BK_VERSION}/bk_${BK_VERSION}_linux_${ARCH}.deb" \
      -o /tmp/bk.deb && \
    dpkg -i /tmp/bk.deb && \
    rm /tmp/bk.deb

# Create non-root user (Claude Code refuses bypassPermissions as root)
RUN useradd -m -s /bin/bash ralph && \
    mkdir -p /workspace && chown ralph:ralph /workspace

USER ralph
RUN git config --global user.email "ralph@buildkite.com" && \
    git config --global user.name "Ralph Wiggum"
WORKDIR /workspace

ENTRYPOINT ["claude"]
