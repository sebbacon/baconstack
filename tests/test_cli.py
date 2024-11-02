import re

from typer.testing import CliRunner

from baconstack.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    pattern = r"baconstack v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(-(?P<release>.*)-(?P<build>\d+))?"
    assert re.match(
        pattern, result.stdout
    ), f"Version '{result.stdout}' does not match the required pattern"
