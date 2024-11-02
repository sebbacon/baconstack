from io import StringIO
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from baconstack.cli import app

runner = CliRunner()


@pytest.fixture
def mock_ssh():
    with patch("paramiko.SSHClient") as mock:
        # Configure the mock to return success for exec_command
        mock_stdin = StringIO()
        mock_stdout = StringIO("Success")
        mock_stderr = StringIO("")
        
        mock.return_value.exec_command.return_value = (
            mock_stdin,
            mock_stdout,
            mock_stderr,
        )
        yield mock


def test_basic_setup(mock_ssh):
    """Test basic app setup with minimal parameters"""
    result = runner.invoke(
        app,
        [
            "setup",
            "testapp",
            "test.example.com",
            "--dokku-host", "dokku.example.com",
        ],
    )
    assert result.exit_code == 0
    
    # Verify SSH connection was attempted
    mock_ssh.return_value.connect.assert_called_once_with(
        "dokku.example.com",
        username="seb",
    )
    
    # Check that basic Dokku commands were executed
    exec_command_calls = mock_ssh.return_value.exec_command.call_args_list
    expected_commands = [
        "sudo dokku apps:create testapp",
        "sudo dokku domains:add testapp test.example.com",
        "sudo dokku storage:ensure-directory testapp",
    ]
    
    for cmd in expected_commands:
        assert any(
            cmd in call.args[0] for call in exec_command_calls
        ), f"Expected command not found: {cmd}"


def test_setup_error_handling(mock_ssh):
    """Test handling of SSH errors during setup"""
    # Configure mock to simulate an error
    mock_ssh.return_value.exec_command.return_value = (
        StringIO(),
        StringIO(),
        StringIO("Error: App already exists"),
    )
    
    result = runner.invoke(
        app,
        [
            "setup",
            "testapp",
            "test.example.com",
            "--dokku-host", "dokku.example.com",
        ],
    )
    
    # Command should complete but show error message
    assert result.exit_code == 0
    assert "Error running" in result.stdout


def test_setup_with_apt_packages(mock_ssh):
    """Test setup with APT packages configuration"""
    with patch("baconstack.cli.read_app_json") as mock_read_json:
        mock_read_json.return_value = {
            "dokku": {
                "apt-packages": ["postgresql-client", "redis-tools"]
            }
        }
        
        result = runner.invoke(
            app,
            [
                "setup",
                "testapp",
                "test.example.com",
                "--dokku-host", "dokku.example.com",
            ],
        )
        
        assert result.exit_code == 0
        
        # Verify APT packages were configured
        exec_command_calls = mock_ssh.return_value.exec_command.call_args_list
        expected_cmd = 'dokku docker-options:add testapp build'
        assert any(
            expected_cmd in call.args[0] for call in exec_command_calls
        ), "APT packages not configured"
