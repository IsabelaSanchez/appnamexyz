import json
import os
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

root = Path("/opt/accessibility")
repository = os.environ["DEPLOY_REPOSITORY"]
branch = os.environ.get("DEPLOY_BRANCH", "main")
public_url = os.environ["PUBLIC_URL"]


def request(path: str) -> dict:
    req = Request(f"https://api.github.com/repos/{repository}/{path}", headers={"Accept": "application/vnd.github+json", "User-Agent": "AccessibleMaterialsDeployment"})
    with urlopen(req, timeout=20) as response:
        return json.load(response)


head = subprocess.check_output(["git", "ls-remote", f"https://github.com/{repository}.git", f"refs/heads/{branch}"], text=True, timeout=30).split()[0]
if not re.fullmatch(r"[a-f0-9]{40}", head):
    raise ValueError("Invalid revision")
current = root / "config/current-release"
if current.exists() and current.read_text().strip() == head:
    raise SystemExit(0)
runs = request(f"actions/workflows/deploy.yml/runs?head_sha={head}&event=push&per_page=5")["workflow_runs"]
validated = False
for run in runs:
    if run["head_branch"] != branch or run["head_repository"]["full_name"] != repository:
        continue
    jobs = request(f"actions/runs/{run['id']}/jobs")["jobs"]
    if any(job["name"] == "validate" and job["conclusion"] == "success" for job in jobs):
        validated = True
        break
if not validated:
    print("Waiting for GitHub Actions validation.")
    raise SystemExit(0)
release = root / "releases" / head
if not release.exists():
    subprocess.run(["git", "clone", "--no-checkout", f"https://github.com/{repository}.git", str(release)], check=True, timeout=120)
    subprocess.run(["git", "-C", str(release), "checkout", "--detach", head], check=True, timeout=30)
subprocess.run(["bash", str(release / "infra/deploy.sh")], env={**os.environ, "RELEASE_TAG": head}, check=True, timeout=1200)
with urlopen(f"{public_url}/api/v1/health", timeout=20) as response:
    health = json.load(response)
if health.get("release") != head:
    raise RuntimeError("Public deployment revision does not match validated source")
print(f"Deployed validated revision {head}.")
