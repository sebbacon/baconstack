# Development
install:
    uv venv --python 3.11
    source .venv/bin/activate
    just requirements
    uv pip install -e ".[dev]"

requirements:
    #!/usr/bin/env bash
    # Generate requirements.txt from pyproject.toml
    uv pip compile pyproject.toml -o requirements.txt
    # Generate requirements-dev.txt from pyproject.toml including dev dependencies
    uv pip compile pyproject.toml --all-extras -o requirements-dev.txt


# Testing and linting
test:
    pytest

lint:
    ruff check .
    ruff format --check .

format:
    ruff check --fix .
    ruff format .

# Version management
version:
    #!/usr/bin/env bash
    # Get the current version from pyproject.toml
    current_version=$(grep -m1 "version = " pyproject.toml | cut -d'"' -f2)
    echo "Current version: ${current_version}"

# Bump the version in setup.py and git tags; part can be major, minor, patch
bump part="minor":
    # Bump version using bump2version
    bump2version {{ part }} --allow-dirty
    echo "Run 'git push && git push --tags' to publish"

