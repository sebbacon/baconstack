# baconstack/cli.py
import json
import os
import subprocess
from pathlib import Path

import digitalocean
import paramiko
import typer
from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer()
console = Console()

app = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo("baconstack v0.1.0")
        raise typer.Exit()


@app.callback()
def common(
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    pass


def read_app_json(project_dir: Path) -> dict:
    """Read and parse app.json file"""
    app_json_path = project_dir / "app.json"
    if not app_json_path.exists():
        return {}
    return json.loads(app_json_path.read_text())


def load_env_file(env_file: Path) -> dict[str, str]:
    """Load environment variables from .env file"""
    if not env_file.exists():
        return {}
    return dotenv_values(env_file)


def filter_sensitive_vars(env_vars: dict[str, str]) -> dict[str, str]:
    """Filter out sensitive variables for display"""
    sensitive_patterns = ["KEY", "SECRET", "PASSWORD", "CREDENTIAL"]
    return {
        k: (
            "*" * 8
            if any(pattern in k.upper() for pattern in sensitive_patterns)
            else v
        )
        for k, v in env_vars.items()
    }


def setup_apt_packages(ssh: paramiko.SSHClient, project_name: str, packages: list[str]):
    """Set up APT packages for Dokku app"""
    if not packages:
        return

    # Configure Dokku to install packages
    packages_str = " ".join(packages)
    cmd = f"sudo dokku docker-options:add {project_name} build '--build-arg DOKKU_APT_PACKAGES={packages_str}'"

    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout_data = stdout.read().decode()
    stderr_data = stderr.read().decode()

    if stdout_data:
        console.print(stdout_data)
    if stderr_data:
        console.print(f"[red]Error configuring APT packages[/red]: {stderr_data}")


def setup_healthcheck(
    project_name: str,
    healthcheck_url: str,
    ssh: paramiko.SSHClient,
):
    """Set up healthcheck monitoring"""
    # Configure zero-downtime deployment checks
    commands = [
        f"dokku checks:enable {project_name}",
        f"dokku checks:run {project_name}",
    ]

    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(f"sudo {cmd}")
        console.print(stdout.read().decode())
        if stderr.read():
            console.print(f"[red]Error running {cmd}[/red]")


@app.command()
def new(
    project_name: str,
    framework: str = typer.Option("fastapi", help="Web framework to use"),
    domain: str = typer.Option(None, help="Domain for deployment"),
    healthcheck_url: str = typer.Option(
        None, help="Healthcheck.io URL for uptime monitoring"
    ),
    description: str = typer.Option(None, help="Project description"),
    author_name: str = typer.Option(None, help="Author name"),
    author_email: str = typer.Option(None, help="Author email"),
    use_loki: bool = typer.Option(True, help="Enable Loki logging"),
):
    """Create a new web project from template"""
    console.print(Panel(f"Creating new {framework} project: {project_name}"))

    template_repo = os.getenv("BACONSTACK_TEMPLATE", "gh:sebbacon/baconstack-template")

    # Use copier to create project from template
    data = {
        "framework": framework,
        "project_name": project_name,
        "domain": domain or f"{project_name}.example.com",
        "healthcheck_url": healthcheck_url or "",
        "project_description": description or f"{framework.title()} Web App",
        "author_name": author_name or "Seb Bacon",
        "author_email": author_email or "seb.bacon@gmail.com",
        "use_loki": use_loki,
    }

    try:
        from copier import run_copy

        run_copy(
            template_repo,
            project_name,
            data=data,
            unsafe=True,
            vcs_ref="HEAD",
        )
        
        # Skip pre-commit if requested
        if os.getenv("SKIP_PRE_COMMIT"):
            return
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error creating project: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def setup(
    project_name: str,
    domain: str,
    dokku_host: str = typer.Option(..., envvar="DOKKU_HOST"),
    dokku_user: str = typer.Option(
        "seb", help="Username for Dokku host SSH connection"
    ),
    do_token: str = typer.Option(
        ..., envvar="DO_API_KEY", help="DigitalOcean API token"
    ),
    healthcheck_url: str = typer.Option(None, envvar="HEALTHCHECK_URL"),
):
    """Set up Dokku app and configure domain"""
    console.print(Panel(f"Setting up {project_name} on {dokku_host}"))

    project_dir = Path(project_name)
    app_config = read_app_json(project_dir)

    # Connect to Dokku host
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(dokku_host, username=dokku_user)

    # Set up APT packages if specified
    apt_packages = app_config.get("dokku", {}).get("apt-packages", [])
    if apt_packages:
        console.print(f"Setting up APT packages: {', '.join(apt_packages)}")
        setup_apt_packages(ssh, project_name, apt_packages)

    # Set up DNS with DigitalOcean
    manager = digitalocean.Manager(token=do_token)
    domain_name = ".".join(domain.split(".")[-2:])
    record_name = domain.split(".")[0]

    # Get domain
    try:
        do_domain = manager.get_domain(domain_name)
    except Exception as e:
        console.print(
            f"[red]Error: Domain {domain_name} not found in DigitalOcean[/red]"
        )
        console.print(f"[red]Details: {str(e)}[/red]")
        raise typer.Exit(1)

    # Create CNAME record
    try:
        do_domain.create_new_domain_record(
            type="CNAME",
            name=record_name,
            data=dokku_host + ".",
        )
        console.print(f"[green]Created DNS record for {domain}[/green]")
    except Exception as e:
        console.print(f"[red]Error creating DNS record: {str(e)}[/red]")
        raise typer.Exit(1)

    # Basic Dokku setup
    commands = [
        f"dokku apps:create {project_name}",
        f"dokku domains:add {project_name} {domain}",
        # Storage setup
        f"dokku storage:ensure-directory {project_name}",
        f"dokku storage:mount {project_name} /var/lib/dokku/data/storage/{project_name}:/app/data",
        # SSL setup
        "dokku plugin:install https://github.com/dokku/dokku-letsencrypt.git",
        f"dokku letsencrypt:set {project_name} email seb@bacon.boutique",
        f"dokku letsencrypt:enable {project_name}",
        f"dokku letsencrypt:auto-renew {project_name}",
    ]

    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(f"sudo {cmd}")
        stdout_data = stdout.read().decode()
        stderr_data = stderr.read().decode()

        if stdout_data:
            console.print(stdout_data)
        if stderr_data:
            console.print(f"[red]Error running {cmd}[/red] {stderr_data}")

    # Set up healthcheck
    if healthcheck_url or app_config.get("healthchecks"):
        setup_healthcheck(project_name, healthcheck_url, ssh)


# Create env command group
app_env = typer.Typer(help="Manage environment variables")
app.add_typer(app_env, name="env")

@app_env.command()
def init(
        project_dir: str = typer.Argument(".", help="Project directory"),
    ):
        """Initialize .env file from template"""
        project_path = Path(project_dir)
        env_example = project_path / ".env.example"
        env_file = project_path / ".env"

        if env_file.exists():
            if not typer.confirm("A .env file already exists. Overwrite?"):
                raise typer.Abort()

        if not env_example.exists():
            console.print("[red]No .env.example file found[/red]")
            raise typer.Abort()

        # Copy template to .env
        env_file.write_text(env_example.read_text())
        console.print("[green]Created .env file from template[/green]")
        console.print("\nPlease edit the .env file and update the values.")

        # Show current variables
        env_vars = load_env_file(env_file)
        table = Table(title="Environment Variables")
        table.add_column("Variable")
        table.add_column("Value")

        filtered_vars = filter_sensitive_vars(env_vars)
        for key, value in filtered_vars.items():
            table.add_row(key, value or "[red]empty[/red]")

        console.print(table)

@app_env.command()
def sync(
        project_name: str,
        dokku_host: str = typer.Option(..., envvar="DOKKU_HOST"),
        env_file: str = typer.Option(".env", help="Path to .env file"),
    ):
        """Sync local environment variables to Dokku"""
        env_path = Path(env_file)
        if not env_path.exists():
            console.print(f"[red]No .env file found at {env_file}[/red]")
            raise typer.Abort()

        # Load environment variables
        env_vars = load_env_file(env_path)

        # Connect to Dokku host
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(dokku_host)

        # Clear existing config
        stdin, stdout, stderr = ssh.exec_command(
            f"sudo dokku config:clear {project_name}"
        )
        if stderr.read():
            console.print("[red]Error clearing existing configuration[/red]")
            return

        # Set new configuration
        config_cmd = f"sudo dokku config:set {project_name}"
        for key, value in env_vars.items():
            if value:  # Only set non-empty values
                config_cmd += f' {key}="{value}"'

        stdin, stdout, stderr = ssh.exec_command(config_cmd)
        if stderr.read():
            console.print("[red]Error setting configuration[/red]")
            return

        # Show current configuration
        stdin, stdout, stderr = ssh.exec_command(
            f"sudo dokku config:show {project_name}"
        )
        config_output = stdout.read().decode()

        table = Table(title=f"Dokku Configuration for {project_name}")
        table.add_column("Variable")
        table.add_column("Value")

        for line in config_output.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip():
                    filtered_value = (
                        "*" * 8
                        if any(
                            pattern in key.upper()
                            for pattern in ["KEY", "SECRET", "PASSWORD", "CREDENTIAL"]
                        )
                        else value.strip()
                    )
                    table.add_row(key.strip(), filtered_value)

        console.print(table)

@app_env.command()
def show(
        project_name: str,
        dokku_host: str = typer.Option(..., envvar="DOKKU_HOST"),
    ):
        """Show current Dokku environment variables"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(dokku_host)

        stdin, stdout, stderr = ssh.exec_command(
            f"sudo dokku config:show {project_name}"
        )
        config_output = stdout.read().decode()

        table = Table(title=f"Dokku Configuration for {project_name}")
        table.add_column("Variable")
        table.add_column("Value")

        for line in config_output.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip():
                    filtered_value = (
                        "*" * 8
                        if any(
                            pattern in key.upper()
                            for pattern in ["KEY", "SECRET", "PASSWORD", "CREDENTIAL"]
                        )
                        else value.strip()
                    )
                    table.add_row(key.strip(), filtered_value)

        console.print(table)



@app.command()
def destroy(
    project_name: str,
    dokku_host: str = typer.Option(..., envvar="DOKKU_HOST"),
    do_token: str = typer.Option(..., envvar="DO_API_KEY"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
):
    """Destroy a Dokku app and remove its DNS record"""
    if not force:
        confirm = typer.confirm(
            f"This will permanently delete the app '{project_name}' and its DNS records. Continue?"
        )
        if not confirm:
            raise typer.Abort()

    # Connect to Dokku host
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(dokku_host)

    # Destroy the Dokku app
    stdin, stdout, stderr = ssh.exec_command(
        f"sudo dokku apps:destroy {project_name} --force"
    )
    stdout_data = stdout.read().decode()
    stderr_data = stderr.read().decode()

    if stdout_data:
        console.print(stdout_data)
    if stderr_data:
        console.print(f"[red]Error destroying app:[/red] {stderr_data}")
        return

    # Remove DNS record from DigitalOcean
    try:
        manager = digitalocean.Manager(token=do_token)
        domains = manager.get_all_domains()

        for domain in domains:
            records = domain.get_records()
            for record in records:
                if record.type == "CNAME" and record.name == project_name:
                    record.destroy()
                    console.print(
                        f"[green]Removed DNS record for {project_name}.{domain.name}[/green]"
                    )
                    return

        console.print("[yellow]No matching DNS records found[/yellow]")

    except Exception as e:
        console.print(f"[red]Error removing DNS record: {str(e)}[/red]")


@app.command()
def setup_loki(
    project_name: str,
    dokku_host: str = typer.Option(..., envvar="DOKKU_HOST"),
):
    """Set up Loki logging for a Dokku app"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(dokku_host)

    commands = [
        "dokku plugin:install https://github.com/dokku/dokku-loki.git",
        f"dokku loki:enable {project_name}",
        f"dokku loki:set {project_name} retention-period 7d",
    ]

    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(f"sudo {cmd}")
        console.print(stdout.read().decode())


if __name__ == "__main__":
    app()
