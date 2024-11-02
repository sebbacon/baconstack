from io import StringIO
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from baconstack.cli import app

runner = CliRunner()


@pytest.fixture
def mock_ssh():
    with patch("paramiko.SSHClient") as mock:
        # Configure the mock to return success for exec_command
        # Mock stdout/stderr as bytes objects
        mock_stdin = StringIO()
        mock_stdout = StringIO()
        mock_stderr = StringIO()
        
        # Configure the mock's read() methods to return bytes
        mock_stdout.read = lambda: b"Success"
        mock_stderr.read = lambda: b""
        
        # Set up the mock to return our configured streams
        mock.return_value.exec_command.return_value = (
            mock_stdin,
            mock_stdout, 
            mock_stderr
        )
        yield mock


def test_basic_setup(mock_ssh):
    """Test basic app setup with minimal parameters"""
    with patch('digitalocean.Manager'):
        result = runner.invoke(
            app,
            [
                "setup",
                "testapp",
                "test.example.com",
                "--dokku-host", "dokku.example.com",
                "--do-token", "fake-token",
                "--do-token", "fake-token"
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
                cmd in str(call) for call in exec_command_calls
            ), f"Expected command not found: {cmd}"


def test_setup_error_handling(mock_ssh):
    """Test handling of SSH errors during setup"""
    with patch('digitalocean.Manager'):
        # Configure mock with error response
        mock_stdin = StringIO()
        mock_stdout = StringIO()
        mock_stderr = StringIO()
        
        def mock_exec(cmd):
            if "apps:create" in cmd:
                mock_stderr.read = lambda: b"Error: App already exists"
                mock_stdout.read = lambda: b""
            else:
                mock_stderr.read = lambda: b""
                mock_stdout.read = lambda: b"Success"
            return mock_stdin, mock_stdout, mock_stderr
            
        mock_ssh.return_value.exec_command = mock_exec
        
        result = runner.invoke(
            app,
            [
                "setup",
                "testapp",
                "test.example.com",
                "--dokku-host", "dokku.example.com",
                "--do-token", "fake-token"
            ],
        )
        
        # Command should complete but show error message
        assert result.exit_code == 0
        assert "Error running dokku apps:create testapp" in result.stdout
        assert "Error: App already exists" in result.stdout


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
