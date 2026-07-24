from config import load_config, DEFAULTS


def test_load_config_returns_defaults_when_missing(tmp_path):
    cfg = load_config(str(tmp_path / "nonexistent.json"))
    assert cfg["countdown_sec"] == DEFAULTS["countdown_sec"]
    assert cfg["camera"]["backend"] == "mock"
    for key in ("camera", "template_path", "slots", "countdown_sec",
                "photo_ratio", "save_path", "trigger_key", "qr_prompt_delay"):
        assert key in cfg


def test_load_config_merges_user_over_defaults(tmp_path):
    import json
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"countdown_sec": 5}), encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg["countdown_sec"] == 5           # user override
    assert cfg["qr_prompt_delay"] == DEFAULTS["qr_prompt_delay"]  # default preserved
