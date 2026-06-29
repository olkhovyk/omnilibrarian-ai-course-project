import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_MCP_PORTS = {
    "bg3": 8765,
    "blue_prince": 8766,
}
MCP_URL_ENV_KEYS = {
    "bg3": "BG3_MCP_URL",
    "blue_prince": "BLUE_PRINCE_MCP_URL",
}


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    command: list[str]
    critical: bool = True


def build_api_command(*, host: str, port: int) -> list[str]:
    return [
        "python",
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_ui_command(*, host: str, port: int, api_url: str) -> list[str]:
    return [
        "streamlit",
        "run",
        "apps/streamlit_app/app.py",
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]


def build_mcp_command(*, game_id: str, host: str, port: int) -> list[str]:
    server_modules = {
        "bg3": "mcp_servers.bg3.server",
        "blue_prince": "mcp_servers.blue_prince.server",
    }
    server_module = server_modules.get(game_id)
    if server_module is None:
        raise ValueError(f"Unsupported MCP game_id for dev runner: {game_id}")
    return [
        "python",
        "-m",
        server_module,
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_process_specs(
    *,
    api_host: str,
    api_port: int,
    ui_host: str,
    ui_port: int,
    include_mcp: bool,
    mcp_game_id: str | None = None,
    mcp_game_ids: list[str] | None = None,
    mcp_host: str,
    mcp_port: int | None = None,
    mcp_ports: dict[str, int] | None = None,
) -> list[ProcessSpec]:
    api_url = f"http://{api_host}:{api_port}/v1/chat"
    specs = [
        ProcessSpec("API", build_api_command(host=api_host, port=api_port)),
        ProcessSpec("UI", build_ui_command(host=ui_host, port=ui_port, api_url=api_url)),
    ]
    if include_mcp:
        game_ids = resolve_mcp_game_ids(mcp_game_id=mcp_game_id, mcp_games=mcp_game_ids)
        ports = resolve_mcp_ports(game_ids=game_ids, single_port=mcp_port, port_overrides=mcp_ports)
        specs.extend(
            ProcessSpec(
                f"MCP {game_id}",
                build_mcp_command(game_id=game_id, host=mcp_host, port=ports[game_id]),
                critical=False,
            )
            for game_id in game_ids
        )
    return specs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OmniLibrarian API, Streamlit UI, and MCP services together.")
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-host", default="127.0.0.1")
    parser.add_argument("--ui-port", type=int, default=8501)
    parser.add_argument("--mcp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--mcp-games",
        default="bg3,blue_prince",
        help="Comma-separated MCP game ids to start when --mcp is enabled.",
    )
    parser.add_argument(
        "--mcp-game-id",
        default=None,
        help="Backward-compatible single MCP game id. Overrides --mcp-games when set.",
    )
    parser.add_argument("--mcp-host", default="127.0.0.1")
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=None,
        help="Port for single-game MCP mode. Multi-game mode uses per-game defaults.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(DOTENV_PATH)

    api_url = f"http://{args.api_host}:{args.api_port}/v1/chat"
    env = os.environ.copy()
    env["PYTHONPATH"] = _prepend_pythonpath(env.get("PYTHONPATH", ""), "src")
    env["OMNILIBRARIAN_API_URL"] = api_url
    env["PYTHONUNBUFFERED"] = "1"
    mcp_game_ids = resolve_mcp_game_ids(
        mcp_game_id=args.mcp_game_id,
        mcp_games=parse_mcp_games(args.mcp_games),
    )
    mcp_ports = resolve_mcp_ports(game_ids=mcp_game_ids, single_port=args.mcp_port)
    if args.mcp:
        apply_mcp_env(env=env, host=args.mcp_host, ports=mcp_ports)

    specs = build_process_specs(
        api_host=args.api_host,
        api_port=args.api_port,
        ui_host=args.ui_host,
        ui_port=args.ui_port,
        include_mcp=args.mcp,
        mcp_game_ids=mcp_game_ids,
        mcp_host=args.mcp_host,
        mcp_ports=mcp_ports,
    )
    processes = [
        subprocess.Popen(
            spec.command,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for spec in specs
    ]
    log_threads = [
        threading.Thread(target=_stream_process_output, args=(spec.name, process), daemon=True)
        for spec, process in zip(specs, processes, strict=True)
    ]
    for thread in log_threads:
        thread.start()

    print(f"API: http://{args.api_host}:{args.api_port}")
    print(f"UI:  http://{args.ui_host}:{args.ui_port}")
    if args.mcp:
        for game_id in mcp_game_ids:
            print(f"MCP: {game_id} http://{args.mcp_host}:{mcp_ports[game_id]}/mcp")
    print("Press Ctrl+C to stop all processes.")

    try:
        warned_noncritical_failures: set[str] = set()
        while True:
            critical_processes_running = True
            for spec, process in zip(specs, processes, strict=True):
                return_code = process.poll()
                if return_code is None:
                    continue
                if spec.critical:
                    critical_processes_running = False
                elif spec.name not in warned_noncritical_failures:
                    warned_noncritical_failures.add(spec.name)
                    print(f"Warning: optional service {spec.name} exited with code {return_code}.")

            if not critical_processes_running:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping OmniLibrarian dev services...")
    finally:
        _terminate_processes(processes)

    failed = collect_failed_critical_processes(specs, processes)
    if failed:
        raise SystemExit(f"One or more dev services exited unexpectedly: {failed}")


def _prepend_pythonpath(existing: str, path: str) -> str:
    if not existing:
        return path
    return f"{path}{os.pathsep}{existing}"


def parse_mcp_games(value: str) -> list[str]:
    game_ids = [part.strip() for part in value.split(",") if part.strip()]
    if not game_ids:
        raise ValueError("--mcp-games must include at least one game id")
    return game_ids


def resolve_mcp_game_ids(*, mcp_game_id: str | None = None, mcp_games: list[str] | None = None) -> list[str]:
    if mcp_game_id:
        return [mcp_game_id]
    return mcp_games or list(DEFAULT_MCP_PORTS)


def resolve_mcp_ports(
    *,
    game_ids: list[str],
    single_port: int | None = None,
    port_overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    ports: dict[str, int] = {}
    for game_id in game_ids:
        if port_overrides and game_id in port_overrides:
            ports[game_id] = port_overrides[game_id]
        elif single_port is not None and len(game_ids) == 1:
            ports[game_id] = single_port
        elif game_id in DEFAULT_MCP_PORTS:
            ports[game_id] = DEFAULT_MCP_PORTS[game_id]
        else:
            raise ValueError(f"No default MCP port configured for game_id: {game_id}")
    return ports


def apply_mcp_env(*, env: dict[str, str], host: str, ports: dict[str, int]) -> None:
    for game_id, port in ports.items():
        env_key = MCP_URL_ENV_KEYS.get(game_id)
        if env_key is None:
            raise ValueError(f"No MCP URL env key configured for game_id: {game_id}")
        env[env_key] = f"http://{host}:{port}/mcp"


def _terminate_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def collect_failed_critical_processes(specs: list[ProcessSpec], processes: list[subprocess.Popen]) -> list[str]:
    return [
        f"{spec.name}={process.returncode}"
        for spec, process in zip(specs, processes, strict=True)
        if spec.critical and process.returncode not in (0, None)
    ]


def _stream_process_output(name: str, process: subprocess.Popen) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        print(format_process_line(name, line), flush=True)


def format_process_line(name: str, line: str) -> str:
    return f"[{name}] {line.rstrip()}"


if __name__ == "__main__":
    main()
