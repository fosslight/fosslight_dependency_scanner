import pytest
import subprocess


@pytest.fixture
def run_command():
    def _run_command(command):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    return _run_command
