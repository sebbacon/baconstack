import re

from typer.testing import CliRunner

from baconstack.cli import app

runner = CliRunner()


from unittest.mock import patch, MagicMock

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
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b""
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""
    mock_ssh_instance.exec_command.return_value = (None, mock_stdout, mock_stderr)

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

@patch("digitalocean.Manager")
@patch("paramiko.SSHClient")
def test_destroy_command(mock_ssh, mock_do_manager):
    # Set up mock SSH client
    mock_ssh_instance = mock_ssh.return_value
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"App destroyed"
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""
    mock_ssh_instance.exec_command.return_value = (None, mock_stdout, mock_stderr)

    # Set up mock DO manager
    mock_manager = mock_do_manager.return_value
    mock_domain = MagicMock()
    mock_record = MagicMock()
    mock_record.type = "CNAME"
    mock_record.name = "testapp"
    mock_domain.get_records.return_value = [mock_record]
    mock_manager.get_all_domains.return_value = [mock_domain]

    result = runner.invoke(
        app,
        [
            "destroy",
            "testapp",
            "--dokku-host", "dokku.example.com",
            "--do-token", "fake-token",
            "--force",
        ],
    )
    assert result.exit_code == 0
    
    # Verify SSH command was executed
    mock_ssh_instance.exec_command.assert_called_with(
        "sudo dokku apps:destroy testapp --force"
    )
    
    # Verify DNS record was destroyed
    mock_record.destroy.assert_called_once()
