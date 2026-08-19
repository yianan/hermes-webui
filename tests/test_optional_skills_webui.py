"""Coverage for discovering and activating on-disk official optional skills."""

from pathlib import Path

from api import routes


SKILL = """---
name: dcf-model
description: Build a DCF workbook.
version: 1.0.0
---

# DCF Model
"""


def _capture_json(monkeypatch):
    captured = {}

    def fake_j(handler, payload, status=200, extra_headers=None):
        captured.update(payload)
        captured["status"] = status
        return payload

    monkeypatch.setattr(routes, "j", fake_j)
    monkeypatch.setattr(
        routes,
        "bad",
        lambda handler, message, status=400: fake_j(handler, {"error": message}, status=status),
    )
    return captured


def test_optional_catalog_lists_uninstalled_on_disk_skill(monkeypatch, tmp_path):
    catalog = tmp_path / "optional-skills"
    skill_dir = catalog / "finance" / "dcf-model"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(SKILL, encoding="utf-8")
    active = tmp_path / "skills"
    active.mkdir()

    monkeypatch.setattr(routes, "_optional_skills_root", lambda: catalog)
    monkeypatch.setattr(routes, "_active_skills_dir", lambda: active)

    items = routes._optional_skills_list()

    assert items == [{
        "name": "dcf-model",
        "description": "Build a DCF workbook.",
        "category": "finance",
        "identifier": "official/finance/dcf-model",
        "installed": False,
    }]


def test_optional_install_copies_complete_skill_into_active_profile(monkeypatch, tmp_path):
    catalog = tmp_path / "optional-skills"
    source = catalog / "finance" / "dcf-model"
    (source / "scripts").mkdir(parents=True)
    (source / "SKILL.md").write_text(SKILL, encoding="utf-8")
    (source / "scripts" / "validate.py").write_text("print('ok')\n", encoding="utf-8")
    active = tmp_path / "skills"
    captured = _capture_json(monkeypatch)
    monkeypatch.setattr(routes, "_optional_skills_root", lambda: catalog)
    monkeypatch.setattr(routes, "_active_skills_dir", lambda: active)

    routes._handle_optional_skill_install(None, {"identifier": "official/finance/dcf-model"})

    installed = active / "finance" / "dcf-model"
    assert captured["ok"] is True
    assert captured["name"] == "dcf-model"
    assert (installed / "SKILL.md").read_text(encoding="utf-8") == SKILL
    assert (installed / "scripts" / "validate.py").is_file()


def test_optional_install_accepts_flat_official_skill(monkeypatch, tmp_path):
    catalog = tmp_path / "optional-skills"
    source = catalog / "yuanbao"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(SKILL, encoding="utf-8")
    active = tmp_path / "skills"
    captured = _capture_json(monkeypatch)
    monkeypatch.setattr(routes, "_optional_skills_root", lambda: catalog)
    monkeypatch.setattr(routes, "_active_skills_dir", lambda: active)

    routes._handle_optional_skill_install(None, {"identifier": "official/yuanbao"})

    assert captured["ok"] is True
    assert captured["identifier"] == "official/yuanbao"
    assert captured["category"] == ""
    assert (active / "yuanbao" / "SKILL.md").is_file()


def test_optional_install_rejects_traversal(monkeypatch):
    captured = _capture_json(monkeypatch)

    routes._handle_optional_skill_install(None, {"identifier": "official/finance/../secrets"})

    assert captured["status"] == 400
    assert captured["error"] == "Invalid official skill identifier"


def test_webui_exposes_optional_catalog_and_install_action():
    route_source = Path("api/routes.py").read_text(encoding="utf-8")
    panel_source = Path("static/panels.js").read_text(encoding="utf-8")

    assert 'parsed.path == "/api/skills/optional"' in route_source
    assert 'parsed.path == "/api/skills/install-optional"' in route_source
    assert "Available to install" in panel_source
    assert "installOptionalSkill" in panel_source
