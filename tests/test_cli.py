import re

from typer.testing import CliRunner

from baconstack.cli import app

runner = CliRunner()


from unittest.mock import patch

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    pattern = r"baconstack v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(-(?P<release>.*)-(?P<build>\d+))?"
    assert re.match(
        pattern, result.stdout
    ), f"Version '{result.stdout}' does not match the required pattern"


@patch("digitalocean.Manager")
@patch("paramiko.SSHClient")
def test_setup_command(mock_ssh, mock_do_manager):
    # Set up mock SSH client
    mock_ssh_instance = mock_ssh.return_value
    mock_ssh_instance.exec_command.return_value = (None, None, None)

    # Set up mock DO manager
    mock_manager = mock_do_manager.return_value
    mock_domain = mock_manager.get_domain.return_value
    mock_domain.create_new_domain_record.return_value = None

    result = runner.invoke(
        app,
        [
            "setup",
            "testapp",
            "test.example.com",
            "--dokku-host", "dokku.example.com",
            "--do-token", "fake-token",
        ],
    )
    assert result.exit_code == 0
