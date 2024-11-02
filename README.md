# baconstack

CLI tool for creating and managing Python web applications with Dokku deployment.

## Installation

```bash
pip install baconstack
```

Optional: Install pre-commit hooks for development:

```bash
pip install pre-commit
pre-commit install
```

## Required Environment Variables

- `DOKKU_HOST`: Your Dokku server hostname
- `DO_API_KEY`: DigitalOcean API token (for DNS management)

Optional:

- `HEALTHCHECK_URL`: URL for uptime monitoring
- `BACONSTACK_TEMPLATE`: Custom template repository (defaults to gh:sebbacon/baconstack-template)

## Quick Start

You'll need to [set up a running dokku server](https://dokku.com/docs/getting-started/installation/). You should set up your ssh so you have passwordless login, and root-equivalent access to the `dokku` command for that account, for example with this `sudoer` config:

    seb ALL=(ALL) NOPASSWD:SETENV: /usr/bin/dokku

Then, on your development machine:

```bash
baconstack new myproject --framework flask --domain myproject.your.dokku.host
cd myproject
just install

# Sets up a new `myproject` dokku up on the dokku host, including ssl
just setup-remote
```

## Usage

### Environment Variables

```bash
# Initialize from template at .env.example
baconstack env init

# Show current Dokku environment variables
baconstack env show PROJECT_NAME

# Sync local .env to Dokku
baconstack env sync PROJECT_NAME
```

### Project Management

```bash
# Create project with options
baconstack new PROJECT_NAME \
  --framework [fastapi|flask|django] \
  --domain example.com \
  --healthcheck-url URL

# Set up Loki logging
baconstack setup-loki PROJECT_NAME

# Remove project and DNS records
baconstack destroy PROJECT_NAME [--force]
```

### Development

```bash
# Install development dependencies
just install

# Run tests
just test

# Run linting
just lint

# Format code
just format

# Show current version
just version

# Bump version (major/minor/patch)
just bump minor
```

## Template Customization

Projects are created from templates with these configurable options:

- Framework selection (fastapi/flask/django)
- Domain configuration
- Healthcheck URL
- Project description
- Author information
- Loki logging setup

## Features

- Zero-downtime deployments with health checks
- SSL/Let's Encrypt automatic setup
- APT package management via app.json
- Persistent storage mounting
- Environment variable management
- DNS management with DigitalOcean
- Loki logging integration
