import asyncio
import importlib
import json
import os
import time
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from pypdf import PdfReader
from app.schemas import Element, Geometry, Representation, Source
from app.refinement import apply_plan, deterministic_plan
from app.storage.local import LocalTemporaryStorageProvider


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.main as module
    monkeypatch.setattr(module, "storage", LocalTemporaryStorageProvider(tmp_path))
    monkeypatch.setattr(module, "state_path", tmp_path / "processing-state.json")
    monkeypatch.setattr(module.settings, "storage_path", tmp_path)
    monkeypatch.setattr(module.settings, "openai_api_key", "")
    module.jobs.clear()
    module.active_projects.clear()
    with TestClient(module.app) as value:
        yield value


def image_bytes():
    image = Image.new("RGB", (500, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(50, 40), (430, 60), (400, 330), (90, 360)], outline="black", width=5)
    draw.line([(100, 80), (170, 160), (130, 240), (220, 320)], fill="black", width=4)
    draw.text((260, 170), "North", fill="black")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def wait(client, project_id, job_id):
    for _ in range(100):
        job = client.get(f"/api/v1/projects/{project_id}/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            assert job["status"] == "completed", job
            return job
        time.sleep(0.05)
    pytest.fail("Job did not complete")


def test_complete_map_workflow_and_actual_exports(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    upload = client.post("/api/v1/projects", files={"file": ("classroom.png", image_bytes(), "image/png")})
    assert upload.status_code == 201
    project = upload.json()
    project_id = project["id"]
    config = project["config"]
    config["engine"] = "opencv"
    assert client.patch(f"/api/v1/projects/{project_id}/configuration", json=config).status_code == 200
    job = client.post(f"/api/v1/projects/{project_id}/analyze").json()
    wait(client, project_id, job["id"])
    rep = client.get(f"/api/v1/projects/{project_id}/representation").json()
    assert len(rep["elements"]) > 0
    element = rep["elements"][0]
    assert client.patch(f"/api/v1/projects/{project_id}/elements/{element['id']}", json={"category": "rivers", "label": "Test river"}).status_code == 200
    job = client.post(f"/api/v1/projects/{project_id}/refine", json={"instruction": "Remove the rivers"}).json()
    wait(client, project_id, job["id"])
    rep = client.get(f"/api/v1/projects/{project_id}/representation").json()
    assert next(e for e in rep["elements"] if e["id"] == element["id"])["visible"] is False
    assert client.post(f"/api/v1/projects/{project_id}/history/undo").status_code == 200
    assert client.post(f"/api/v1/projects/{project_id}/history/redo").status_code == 200
    for format_id in ("svg", "pdf", "png"):
        result = client.post(f"/api/v1/projects/{project_id}/exports/{format_id}")
        assert result.status_code == 200, result.text
        content = client.get(result.json()["url"]).content
        assert len(content) > 100
        if format_id == "svg":
            assert ElementTree.fromstring(content).tag.endswith("svg")
        elif format_id == "pdf":
            assert len(PdfReader(BytesIO(content)).pages) == 1
        else:
            with Image.open(BytesIO(content)) as image:
                assert image.format == "PNG"
                assert image.width == 1800
    assert client.post("/api/v1/disable").json()["enabled"] is False
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 503
    assert client.post(f"/api/v1/projects/{project_id}/refine", json={"instruction": "Show rivers"}).status_code == 503
    assert client.get(f"/api/v1/projects/{project_id}/preview").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/downloads/svg").status_code == 200
    assert client.post("/api/v1/enable").json()["enabled"] is True


def test_upload_validation_and_project_isolation(client):
    assert client.post("/api/v1/projects", files={"file": ("bad.png", b"not an image", "image/png")}).status_code == 422
    assert client.get("/api/v1/projects/not-a-project").status_code == 404
    assert client.get("/api/v1/engines").json()[1]["available"] is False


def test_switch_is_written_to_persistent_state(client, tmp_path):
    client.post("/api/v1/disable")
    assert json.loads((tmp_path / "processing-state.json").read_text()) == {"enabled": False}
    assert client.get("/api/v1/health").status_code == 200


def test_temporary_cleanup_preserves_active_projects(tmp_path):
    storage = LocalTemporaryStorageProvider(tmp_path)
    old = tmp_path / "old"
    active = tmp_path / "active"
    old.mkdir()
    active.mkdir()
    os.utime(old, (0, 0))
    os.utime(active, (0, 0))
    assert storage.cleanup({"active"}) == 1
    assert active.exists()


def test_structured_edits_and_escaping():
    from app.exporters.render import render_svg
    rep = Representation(project_id="test", source=Source(filename="test", width=500, height=400, mime_type="image/png"), elements=[Element(id="river", category="rivers", geometry=Geometry(type="polyline", coordinates=[[0.1, 0.1], [0.5, 0.5]]), label='<script>alert("x")</script>', confidence=0.5, provenance="test")])
    plan = deterministic_plan("Remove the rivers")
    changed = apply_plan(rep, plan)
    assert not changed.elements[0].visible
    assert rep.elements[0].visible
    assert '<script>' not in render_svg(rep)
    assert deterministic_plan("Remove rivers but keep the main river") is None


def test_mocked_openai_analysis_validates_representation(client, monkeypatch):
    import app.analyzers.engines as module
    from app.schemas import Interpretation
    async def mock_analysis(self, image, config):
        return Interpretation(map_type="educational", description="A synthetic river.", warnings=["Synthetic test"], elements=[Element(id="river", category="rivers", geometry=Geometry(type="polyline", coordinates=[[0.2, 0.1], [0.4, 0.8]]), confidence=0.7, provenance="mock")])
    monkeypatch.setattr(module.OpenAIEngine, "analyze", mock_analysis)
    project = client.post("/api/v1/projects", files={"file": ("test.png", image_bytes(), "image/png")}).json()
    config = project["config"]
    config["engine"] = "openai"
    client.patch(f"/api/v1/projects/{project['id']}/configuration", json=config)
    job = client.post(f"/api/v1/projects/{project['id']}/analyze").json()
    wait(client, project["id"], job["id"])
    rep = client.get(f"/api/v1/projects/{project['id']}/representation").json()
    assert rep["elements"][0]["category"] == "rivers"
