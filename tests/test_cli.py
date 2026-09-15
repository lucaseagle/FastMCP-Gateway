import json


def test_init_is_idempotent_and_generates_unique_secret(tmp_path, monkeypatch):
    from fastmcp_gateway.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    first = (tmp_path / ".env").read_text()
    assert "GATEWAY_TOKEN=" in first
    assert main(["init"]) == 0
    assert (tmp_path / ".env").read_text() == first


def test_har_import_does_not_replay_requests(tmp_path, capsys):
    from fastmcp_gateway.cli import main

    path = tmp_path / "capture.har"
    path.write_text(json.dumps({"log": {"entries": []}}))
    assert (
        main(["import-har", str(path), "--origin", "https://example.com", "--name", "example"]) == 0
    )
    assert json.loads(capsys.readouterr().out)["sites"][0]["approved"] is False


def test_local_catalog_commands_and_validation(tmp_path, monkeypatch, capsys):
    from fastmcp_gateway.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GATEWAY_TOKEN", "isolated-cli-test-token-with-32-characters")
    monkeypatch.setenv("GATEWAY_MODE", "development")
    main(["init"])
    capsys.readouterr()
    assert main(["validate"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    assert main(["sites"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["name"] == "catalog"
    assert main(["operations", "catalog"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["name"] == "search"
    assert main(["call", "catalog", "search", "--params", '{"q":123}']) == 1
    assert "configuration_or_input_error" in capsys.readouterr().err
    assert main(["call", "catalog", "missing"]) == 1
    assert "not_found" in capsys.readouterr().err
