import argparse
import getpass
import shlex
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--identity-file", required=True)
    arguments = parser.parse_args()
    api_key = getpass.getpass("OpenAI API key (hidden): ").strip()
    if len(api_key) < 20 or "\n" in api_key or "\r" in api_key:
        raise ValueError("Enter a valid OpenAI API key.")
    remote_program = '''import os
import shlex
import subprocess
import sys
from pathlib import Path
config = Path("/opt/accessibility/config/application.env")
key = sys.stdin.read().strip()
lines = [line for line in config.read_text().splitlines() if not line.startswith("OPENAI_API_KEY=")]
lines.append("OPENAI_API_KEY=" + shlex.quote(key))
config.write_text("\\n".join(lines) + "\\n")
config.chmod(0o600)
release = Path("/opt/accessibility/config/current-release").read_text().strip()
environment = {**os.environ, "APP_ENV_FILE": str(config), "RELEASE_TAG": release}
subprocess.run(["docker", "compose", "--env-file", str(config), "-f", "/opt/accessibility/current/infra/docker-compose.yml", "up", "-d", "--no-build", "--wait", "backend"], env=environment, check=True)
print("OpenAI key configured. Backend restarted without rebuilding.")
'''
    command = f"sudo python3 -c {shlex.quote(remote_program)}"
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=yes", "-i", arguments.identity_file, arguments.host, command], input=api_key, text=True, check=True)


if __name__ == "__main__":
    main()
