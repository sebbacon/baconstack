import os
import subprocess
import time
import requests
from urllib.error import URLError
from urllib.request import urlopen


def wait_for_server(url, timeout=10, interval=0.5):
    """Wait for server to start responding, with timeout"""
    start_time = time.time()
    while True:
        try:
            # Use requests with SSL verification disabled for testing
            response = requests.get(url, verify=False)
            response.raise_for_status()
            return True
        except (requests.RequestException, ConnectionError):
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Server did not respond within {timeout} seconds")
            time.sleep(interval)


import pytest
import tempfile
import shutil
import signal
from pathlib import Path
from typer.testing import CliRunner
from baconstack.cli import app


@pytest.fixture
def project_dir():
    # Create a temporary directory for the test project
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir)


def test_flask_template(project_dir):
    # Generate project using CLI
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        app,
        [
            "new",
            "test_project",
            "--framework",
            "flask",
            "--domain",
            "test.example.com",
        ],
        env={"COPIER_NOT_A_TTY": "1", "SKIP_PRE_COMMIT": "1"},
    )
    if result.exit_code != 0:
        print("CLI Output:", result.stdout)
        print("CLI Errors:", result.stderr)
    assert result.exit_code == 0 or "pre-commit" in result.stdout

    # Move generated project to test directory
    assert os.path.exists("test_project"), "'test_project/' was not created"
    shutil.move("test_project", project_dir + "/test_project")
    project_dir = os.path.join(project_dir, "test_project")

    # Change to project directory
    original_dir = os.getcwd()
    os.chdir(project_dir)

    try:
        # Activate virtual environment and run tests
        venv_path = os.path.join(project_dir, ".venv")
        if os.name == "nt":  # Windows
            activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
            activate_cmd = f"call {activate_script} && "
        else:  # Unix-like
            activate_script = os.path.join(venv_path, "bin", "activate")
            activate_cmd = f"source {activate_script} && "

        # Run tests first
        subprocess.run(activate_cmd + "just install", shell=True, check=True)

        subprocess.run(activate_cmd + "just test", shell=True, check=True)

        # Start the Flask app in the background
        process = subprocess.Popen(
            activate_cmd + "just dev",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,  # Create new process group
        )

        try:
            # Wait for server to start
            wait_for_server("http://localhost:8001", timeout=10)
            # Test if server is responding
            response = requests.get("http://localhost:8001")
            assert response.status_code == 200
        finally:
            # Cleanup: kill the server process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait()

    finally:
        # Return to original directory
        os.chdir(original_dir)


@pytest.mark.skipif(
    not os.getenv("DOKKU_HOST"),
    reason="DOKKU_HOST and DO_API_KEY environment variables required for deployment test",
)
def test_dokku_deployment(project_dir):
    test_app_name = f"testapp{int(time.time())}"  # Unique name for each test run

    # Generate project using CLI
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "new",
            test_app_name,
            "--framework",
            "flask",
            "--domain",
            f"{test_app_name}.{os.getenv('DOKKU_HOST')}",
        ],
    )
    assert result.exit_code == 0

    # Move generated project to test directory
    shutil.move(test_app_name, project_dir + f"/{test_app_name}")
    project_dir = os.path.join(project_dir, test_app_name)

    # Change to project directory
    original_dir = os.getcwd()
    os.chdir(project_dir)

    try:

        # Set up remote and deploy
        subprocess.run(["just", "setup-remote"], check=True)
        subprocess.run(["just", "deploy"], check=True)
        # Wait for deployment to complete and server to respond
        url = f"https://{test_app_name}.{os.getenv('DOKKU_HOST')}"
        wait_for_server(url, timeout=30)  # Allow longer timeout for initial deployment
        response = requests.get(url, verify=False)
        print(response)
        assert response.status_code == 200

    finally:
        try:
            # Cleanup: Remove the test app using CLI destroy command
            runner = CliRunner()
            result = runner.invoke(
                app,
                ["destroy", test_app_name, "--force"],
                env={"DOKKU_HOST": os.getenv("DOKKU_HOST"), "DO_API_KEY": os.getenv("DO_API_KEY")},
            )
            if result.exit_code != 0:
                print(f"Warning: Failed to cleanup test app {test_app_name}")
                print("Error:", result.stdout)
        finally:
            # Return to original directory
            os.chdir(original_dir)
