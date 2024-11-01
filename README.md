# baconstack

A CLI tool for creating and managing Python web applications with integrated Dokku deployment.

## Features

- 🎯 Project creation from customizable templates
- 🚀 Automated Dokku setup and deployment
- 📦 Modern dependency management with uv
- 🔄 Zero-downtime deployments with health checks
- 🔍 Built-in logging with Loki support
- 🔐 Environment variable management
- 🌐 DNS management with DigitalOcean
- ⚙️ APT package management for Dokku apps

## Installation

```bash
# Using uv (recommended)
uv pip install baconstack

# Or using pip
pip install baconstack
```

## Quick Start

```bash
# Set up environment variables
export DOKKU_HOST=your.dokku.host
export DO_API_KEY=your_digitalocean_token  # Optional, for DNS management

# Create a new project
baconstack new myproject --framework fastapi

# Initialize environment variables
cd myproject
baconstack env init

# Edit your .env file
editor .env

# Set up Dokku app
baconstack setup myproject myproject.example.com

# Sync environment variables to Dokku
baconstack env sync myproject

# Optional: Set up Loki logging
baconstack setup-loki myproject
```

## Commands

### Project Creation

```bash
# Create a new project
baconstack new PROJECT_NAME [OPTIONS]

Options:
  --framework [fastapi|flask|django]  Web framework to use (default: fastapi)
  --domain TEXT                      Domain for deployment
  --healthcheck-url TEXT            Healthcheck.io URL for uptime monitoring
```

### Dokku Setup

```bash
# Set up a new Dokku app
baconstack setup PROJECT_NAME DOMAIN [OPTIONS]

Options:
  --dokku-host TEXT      Dokku host (or set DOKKU_HOST env var)
  --do-token TEXT        DigitalOcean API token (or set DO_API_KEY env var)
  --healthcheck-url TEXT Healthcheck.io URL
```

### Environment Variables

```bash

```
