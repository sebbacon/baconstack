import os
import subprocess
import time
import requests
import pytest
from copier import run_copy
import tempfile
import shutil
import signal
from pathlib import Path


@pytest.fixture
def project_dir():
    # Create a temporary directory for the test project
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir)


def test_flask_template(project_dir):
    # Generate project from template
    run_copy(
        ".",
        project_dir,
        data={
            "project_name": "test_project",
            "framework": "flask",
            "project_description": "Test Flask App",
            "domain": "test.example.com",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "use_loki": False,
        },
        unsafe=True,
        vcs_ref="HEAD",
    )

    # Change to project directory
    original_dir = os.getcwd()
    os.chdir(project_dir)

    try:
        # Start the Flask app in the background
        process = subprocess.Popen(
            ["just", "dev"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,  # Create new process group
        )

        # Wait for server to start
        time.sleep(2)

        try:
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
    not os.getenv("DOKKU_HOST") or not os.getenv("TEST_DOMAIN"),
    reason="DOKKU_HOST and TEST_DOMAIN environment variables required for deployment test",
)
def test_dokku_deployment(project_dir):
    test_app_name = f"testapp{int(time.time())}"  # Unique name for each test run

    # Generate project from template
    run_copy(
        ".",
        project_dir,
        data={
            "project_name": test_app_name,
            "framework": "flask",
            "project_description": "Test Flask App",
            "domain": f"{test_app_name}.{os.getenv('TEST_DOMAIN')}",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "use_loki": False,
        },
        unsafe=True,
        vcs_ref="HEAD",
    )

    # Change to project directory
    original_dir = os.getcwd()
    os.chdir(project_dir)

    try:

        # Set up remote and deploy
        subprocess.run(["just", "setup-remote"], check=True)
        subprocess.run(["just", "deploy"], check=True)
        print(11111)
        # Wait for deployment to complete
        time.sleep(8)  # Give it some time to deploy
        print(22222)
        # Test if the app is responding
        url = f"https://{test_app_name}.{os.getenv('TEST_DOMAIN')}"
        response = requests.get(url, timeout=30)
        print(response)
        assert response.status_code == 200

    finally:
        try:
            # Cleanup: Remove the test app from Dokku
            subprocess.run(
                [
                    "ssh",
                    "seb@" + os.getenv("DOKKU_HOST"),
                    f"dokku apps:destroy {test_app_name}",
                    "--force",
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            print(f"Warning: Failed to cleanup test app {test_app_name}")

        # Return to original directory
        os.chdir(original_dir)
