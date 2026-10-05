import pytest


@pytest.fixture(autouse=True)
def _saves_in_a_temp_dir(tmp_path, monkeypatch):
    from gartok import persist
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path / "saves"))
