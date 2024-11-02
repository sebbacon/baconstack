from typer.testing import CliRunner
from baconstack.cli import app

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "baconstack v0.1.0" in result.stdout
