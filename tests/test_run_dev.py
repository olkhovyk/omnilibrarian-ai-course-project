import importlib.util
from pathlib import Path


def _load_run_dev_module():
    module_path = Path("scripts") / "run_dev.py"
    spec = importlib.util.spec_from_file_location("run_dev", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_api_command_uses_uvicorn_with_expected_host_and_port():
    run_dev = _load_run_dev_module()

    command = run_dev.build_api_command(host="127.0.0.1", port=8000)

    assert command == [
        "python",
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]


def test_build_ui_command_uses_streamlit_with_api_url():
    run_dev = _load_run_dev_module()

    command = run_dev.build_ui_command(
        host="127.0.0.1",
        port=8501,
        api_url="http://127.0.0.1:8000/v1/chat",
    )

    assert command == [
        "streamlit",
        "run",
        "apps/streamlit_app/app.py",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        "8501",
    ]


def test_build_mcp_command_runs_bg3_mcp_server_module():
    run_dev = _load_run_dev_module()

    command = run_dev.build_mcp_command(game_id="bg3", host="127.0.0.1", port=8765)

    assert command == [
        "python",
        "-m",
        "mcp_servers.bg3.server",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ]


def test_build_mcp_command_runs_blue_prince_mcp_server_module():
    run_dev = _load_run_dev_module()

    command = run_dev.build_mcp_command(game_id="blue_prince", host="127.0.0.1", port=8766)

    assert command == [
        "python",
        "-m",
        "mcp_servers.blue_prince.server",
        "--host",
        "127.0.0.1",
        "--port",
        "8766",
    ]


def test_build_process_specs_includes_mcp_by_default():
    run_dev = _load_run_dev_module()

    specs = run_dev.build_process_specs(
        api_host="127.0.0.1",
        api_port=8000,
        ui_host="127.0.0.1",
        ui_port=8501,
        include_mcp=True,
        mcp_host="127.0.0.1",
    )

    assert [spec.name for spec in specs] == ["API", "UI", "MCP bg3", "MCP blue_prince"]
    assert [spec.command[-1] for spec in specs[2:]] == ["8765", "8766"]
    assert [spec.critical for spec in specs] == [True, True, False, False]


def test_build_process_specs_can_run_single_mcp_server_for_backward_compatibility():
    run_dev = _load_run_dev_module()

    specs = run_dev.build_process_specs(
        api_host="127.0.0.1",
        api_port=8000,
        ui_host="127.0.0.1",
        ui_port=8501,
        include_mcp=True,
        mcp_game_id="blue_prince",
        mcp_host="127.0.0.1",
        mcp_port=8770,
    )

    assert [spec.name for spec in specs] == ["API", "UI", "MCP blue_prince"]
    assert specs[2].command == [
        "python",
        "-m",
        "mcp_servers.blue_prince.server",
        "--host",
        "127.0.0.1",
        "--port",
        "8770",
    ]


def test_apply_mcp_env_sets_urls_for_all_started_mcp_servers():
    run_dev = _load_run_dev_module()
    env = {}

    run_dev.apply_mcp_env(
        env=env,
        host="127.0.0.1",
        ports={"bg3": 8765, "blue_prince": 8766},
    )

    assert env == {
        "BG3_MCP_URL": "http://127.0.0.1:8765/mcp",
        "BLUE_PRINCE_MCP_URL": "http://127.0.0.1:8766/mcp",
    }


def test_failed_optional_process_does_not_mark_dev_stack_failed():
    run_dev = _load_run_dev_module()

    specs = [
        run_dev.ProcessSpec("API", ["api"], critical=True),
        run_dev.ProcessSpec("MCP bg3", ["mcp"], critical=False),
    ]
    processes = [
        type("Process", (), {"returncode": None})(),
        type("Process", (), {"returncode": 1})(),
    ]

    assert run_dev.collect_failed_critical_processes(specs, processes) == []


def test_failed_critical_process_marks_dev_stack_failed():
    run_dev = _load_run_dev_module()

    specs = [
        run_dev.ProcessSpec("API", ["api"], critical=True),
        run_dev.ProcessSpec("MCP bg3", ["mcp"], critical=False),
    ]
    processes = [
        type("Process", (), {"returncode": 1})(),
        type("Process", (), {"returncode": 1})(),
    ]

    assert run_dev.collect_failed_critical_processes(specs, processes) == ["API=1"]


def test_format_process_line_prefixes_service_name():
    run_dev = _load_run_dev_module()

    assert run_dev.format_process_line("API", "Application startup complete.\n") == "[API] Application startup complete."
