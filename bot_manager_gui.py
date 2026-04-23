from __future__ import annotations

import json
import posixpath
import queue
import re
import shlex
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    import paramiko
except ImportError:  # pragma: no cover - handled in UI at runtime
    paramiko = None


CONFIG_PATH = Path(__file__).with_name("bot_manager_gui_config.json")
WINDOW_TITLE = "Discord Alice Remote Manager"
ANSI_ESCAPE_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1B\\))"
)

DEFAULT_CONFIG = {
    "host": "",
    "port": "22",
    "username": "alicebot",
    "password": "",
    "key_path": "",
    "project_dir": "/home/alicebot/discord_alice",
    "save_password": False,
}


class RemoteSSHClient:
    def __init__(self, settings: dict[str, str | bool]) -> None:
        self.settings = settings

    def _connect(self):
        if paramiko is None:
            raise RuntimeError(
                "Paramiko is not installed. Run: python -m pip install -r manager_requirements.txt"
            )

        host = str(self.settings["host"]).strip()
        username = str(self.settings["username"]).strip()
        project_dir = str(self.settings["project_dir"]).strip()
        if not host:
            raise ValueError("Host is required.")
        if not username:
            raise ValueError("Username is required.")
        if not project_dir:
            raise ValueError("Remote project directory is required.")

        try:
            port = int(str(self.settings["port"]).strip())
        except ValueError as exc:
            raise ValueError("Port must be an integer.") from exc

        key_path = str(self.settings["key_path"]).strip()
        password = str(self.settings["password"])

        client = paramiko.SSHClient()
        # Auto-accept keeps first-time setup simple on Windows.
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 15,
            "allow_agent": True,
            "look_for_keys": True,
        }

        if key_path:
            connect_kwargs["key_filename"] = key_path
        if password:
            connect_kwargs["password"] = password

        client.connect(**connect_kwargs)
        return client

    def stream_command(self, command: str, output_callback) -> int:
        client = self._connect()
        try:
            _, stdout, stderr = client.exec_command(command, get_pty=False)
            channel = stdout.channel

            while True:
                had_output = False

                while channel.recv_ready():
                    cleaned = self._sanitize_output(
                        channel.recv(4096).decode("utf-8", errors="replace")
                    )
                    if cleaned:
                        output_callback(cleaned)
                    had_output = True

                while channel.recv_stderr_ready():
                    cleaned = self._sanitize_output(
                        channel.recv_stderr(4096).decode("utf-8", errors="replace")
                    )
                    if cleaned:
                        output_callback(cleaned)
                    had_output = True

                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break

                if not had_output:
                    time.sleep(0.1)

            return channel.recv_exit_status()
        finally:
            client.close()

    @staticmethod
    def _sanitize_output(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = ANSI_ESCAPE_RE.sub("", text)
        return "".join(
            character
            for character in text
            if character in ("\n", "\t") or ord(character) >= 32
        )

    def download_file(self, remote_path: str, local_path: str) -> None:
        client = self._connect()
        sftp = None
        try:
            sftp = client.open_sftp()
            sftp.get(remote_path, local_path)
        finally:
            if sftp is not None:
                sftp.close()
            client.close()


class BotManagerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1040x720")

        self.message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.current_worker: threading.Thread | None = None

        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.key_path_var = tk.StringVar()
        self.project_dir_var = tk.StringVar()
        self.save_password_var = tk.BooleanVar(value=False)

        self.action_buttons: list[ttk.Button] = []
        self.status_var = tk.StringVar(value="Idle.")

        self._build_ui()
        self._load_config()
        self.root.after(100, self._drain_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        connection_frame = ttk.LabelFrame(self.root, text="Connection")
        connection_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 8))
        for column in range(3):
            connection_frame.columnconfigure(column, weight=1)

        self._add_labeled_entry(connection_frame, "Host", self.host_var, 0)
        self._add_labeled_entry(connection_frame, "Port", self.port_var, 1)
        self._add_labeled_entry(connection_frame, "Username", self.username_var, 2)
        self._add_labeled_entry(
            connection_frame,
            "Password / key passphrase",
            self.password_var,
            3,
            show="*",
        )
        self._add_key_path_row(connection_frame, 4)
        self._add_labeled_entry(
            connection_frame,
            "Remote project dir",
            self.project_dir_var,
            5,
        )

        remember_check = ttk.Checkbutton(
            connection_frame,
            text="Save password in local config",
            variable=self.save_password_var,
        )
        remember_check.grid(row=6, column=0, sticky="w", padx=8, pady=(4, 8))

        button_row = ttk.Frame(connection_frame)
        button_row.grid(row=6, column=1, columnspan=2, sticky="e", padx=8, pady=(4, 8))
        ttk.Button(button_row, text="Save settings", command=self._save_config).grid(row=0, column=0, padx=(0, 8))
        test_button = ttk.Button(button_row, text="Test SSH", command=self._test_connection)
        test_button.grid(row=0, column=1)
        self.action_buttons.append(test_button)

        actions_frame = ttk.LabelFrame(self.root, text="Actions")
        actions_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        for column in range(4):
            actions_frame.columnconfigure(column, weight=1)

        self._add_action_button(actions_frame, "Show status", 0, 0, self._show_status)
        self._add_action_button(actions_frame, "Start bot", 0, 1, self._start_bot)
        self._add_action_button(actions_frame, "Stop bot", 0, 2, self._stop_bot)
        self._add_action_button(actions_frame, "Restart bot", 0, 3, self._restart_bot)
        self._add_action_button(actions_frame, "Update code", 1, 0, self._update_code)
        self._add_action_button(actions_frame, "Update + sync deps", 1, 1, self._update_and_sync)
        self._add_action_button(actions_frame, "Tail API log", 1, 2, self._tail_api_log)
        self._add_action_button(actions_frame, "Download API log", 1, 3, self._download_api_log)

        output_frame = ttk.LabelFrame(self.root, text="Output")
        output_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=24)
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.output_text.configure(state=tk.DISABLED)

        output_buttons = ttk.Frame(output_frame)
        output_buttons.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        output_buttons.columnconfigure(0, weight=1)

        ttk.Label(output_buttons, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(output_buttons, text="Clear output", command=self._clear_output).grid(row=0, column=1, sticky="e")

    def _add_labeled_entry(
        self,
        parent,
        label: str,
        variable: tk.StringVar,
        row: int,
        show: str | None = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=(8, 0))
        entry = ttk.Entry(parent, textvariable=variable, show=show or "")
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=(0, 4))

    def _add_key_path_row(self, parent, row: int) -> None:
        ttk.Label(parent, text="Private key path (optional)").grid(
            row=row, column=0, sticky="w", padx=8, pady=(8, 0)
        )
        entry = ttk.Entry(parent, textvariable=self.key_path_var)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=(0, 4))
        ttk.Button(parent, text="Browse", command=self._browse_key_path).grid(
            row=row, column=2, sticky="ew", padx=8, pady=(0, 4)
        )

    def _add_action_button(self, parent, text: str, row: int, column: int, command) -> None:
        button = ttk.Button(parent, text=text, command=command)
        button.grid(row=row, column=column, sticky="ew", padx=8, pady=8)
        self.action_buttons.append(button)

    def _browse_key_path(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select private key",
            filetypes=[("Private keys", "*"), ("All files", "*.*")],
        )
        if file_path:
            self.key_path_var.set(file_path)

    def _save_config(self, announce: bool = True) -> None:
        config = self._collect_settings()
        if not self.save_password_var.get():
            config["password"] = ""
        CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
        if announce:
            self._append_output(f"Saved local settings to {CONFIG_PATH.name}.\n")

    def _load_config(self) -> None:
        config = dict(DEFAULT_CONFIG)
        if CONFIG_PATH.exists():
            try:
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

        self.host_var.set(str(config.get("host", DEFAULT_CONFIG["host"])))
        self.port_var.set(str(config.get("port", DEFAULT_CONFIG["port"])))
        self.username_var.set(str(config.get("username", DEFAULT_CONFIG["username"])))
        self.password_var.set(str(config.get("password", DEFAULT_CONFIG["password"])))
        self.key_path_var.set(str(config.get("key_path", DEFAULT_CONFIG["key_path"])))
        self.project_dir_var.set(str(config.get("project_dir", DEFAULT_CONFIG["project_dir"])))
        self.save_password_var.set(bool(config.get("save_password", DEFAULT_CONFIG["save_password"])))

    def _collect_settings(self) -> dict[str, str | bool]:
        return {
            "host": self.host_var.get().strip(),
            "port": self.port_var.get().strip(),
            "username": self.username_var.get().strip(),
            "password": self.password_var.get(),
            "key_path": self.key_path_var.get().strip(),
            "project_dir": self.project_dir_var.get().strip(),
            "save_password": self.save_password_var.get(),
        }

    def _set_busy(self, busy: bool, status_text: str) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for button in self.action_buttons:
            button.configure(state=state)
        self.status_var.set(status_text)

    def _queue_text(self, text: str) -> None:
        self.message_queue.put(("text", text))

    def _queue_done(self, title: str, exit_code: int | None, is_error: bool) -> None:
        self.message_queue.put(("done", {"title": title, "exit_code": exit_code, "is_error": is_error}))

    def _run_command_action(self, title: str, command: str) -> None:
        self._start_background_task(title, lambda: self._execute_remote_command(title, command))

    def _start_background_task(self, title: str, task) -> None:
        if self.current_worker and self.current_worker.is_alive():
            messagebox.showinfo(WINDOW_TITLE, "Another action is still running.")
            return

        self._save_config(announce=False)
        self._set_busy(True, f"{title}...")
        self._append_output(f"\n=== {title} ===\n")

        def runner() -> None:
            try:
                task()
            except Exception as exc:  # pragma: no cover - UI error path
                self._queue_text(f"\nERROR: {exc}\n")
                self._queue_done(title, None, True)

        self.current_worker = threading.Thread(target=runner, daemon=True)
        self.current_worker.start()

    def _execute_remote_command(self, title: str, command: str) -> None:
        client = RemoteSSHClient(self._collect_settings())
        exit_code = client.stream_command(command, self._queue_text)
        self._queue_text(f"\nExit code: {exit_code}\n")
        self._queue_done(title, exit_code, exit_code != 0)

    def _download_api_log(self) -> None:
        settings = self._collect_settings()
        filename = filedialog.asksaveasfilename(
            title="Save API log",
            defaultextension=".jsonl",
            initialfile="api_logs.jsonl",
            filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
        )
        if not filename:
            return

        def task() -> None:
            client = RemoteSSHClient(settings)
            remote_path = posixpath.join(str(settings["project_dir"]), "api_logs.jsonl")
            client.download_file(remote_path, filename)
            self._queue_text(f"Downloaded {remote_path} to {filename}\n")
            self._queue_done("Download API log", 0, False)

        self._start_background_task("Download API log", task)

    def _test_connection(self) -> None:
        command = self._build_project_command(
            "printf 'Connected as: '; whoami; "
            "printf '\\nRemote host: '; hostname; "
            "printf '\\nProject dir: '; pwd; "
            "printf '\\nGit HEAD: '; git -c color.ui=never --no-pager log -1 --oneline || true; "
            "printf '\\n'"
        )
        self._run_command_action("Test SSH", command)

    def _show_status(self) -> None:
        command = self._build_project_command(
            "printf 'Project directory: '; pwd; "
            "printf '\\n\\nGit status:\\n'; git -c color.ui=never status --short || true; "
            "printf '\\nLast commit:\\n'; git -c color.ui=never --no-pager log -1 --oneline || true; "
            "printf '\\n\\nScreen sessions:\\n'; screen -ls || true"
        )
        self._run_command_action("Show status", command)

    def _start_bot(self) -> None:
        command = self._build_project_command(
            "if screen -list | grep -q '[.]discord_alice'; then "
            "echo 'discord_alice is already running.'; "
            "else "
            "screen -dmS discord_alice bash -lc 'source venv/bin/activate && python3 bot.py'; "
            "echo 'Bot started.'; "
            "fi"
        )
        self._run_command_action("Start bot", command)

    def _stop_bot(self) -> None:
        command = self._build_project_command(
            "screen -S discord_alice -X quit || true; "
            "echo 'Stop command sent.'"
        )
        self._run_command_action("Stop bot", command)

    def _restart_bot(self) -> None:
        command = self._build_project_command(
            "screen -S discord_alice -X quit || true; "
            "screen -dmS discord_alice bash -lc 'source venv/bin/activate && python3 bot.py'; "
            "echo 'Bot restarted.'"
        )
        self._run_command_action("Restart bot", command)

    def _update_code(self) -> None:
        self._run_command_action("Update code", self._build_project_command("./update.sh"))

    def _update_and_sync(self) -> None:
        self._run_command_action(
            "Update + sync deps",
            self._build_project_command("./update.sh --sync-deps"),
        )

    def _tail_api_log(self) -> None:
        command = self._build_project_command(
            "if [ -f api_logs.jsonl ]; then "
            "tail -n 200 api_logs.jsonl; "
            "else "
            "echo 'api_logs.jsonl not found.'; "
            "fi"
        )
        self._run_command_action("Tail API log", command)

    def _build_project_command(self, inner_command: str) -> str:
        project_dir = self.project_dir_var.get().strip()
        script = (
            "export TERM=dumb PAGER=cat GIT_PAGER=cat LESS=FRX LANG=C.UTF-8 LC_ALL=C.UTF-8; "
            f"cd {shlex.quote(project_dir)} && {inner_command}"
        )
        return f"bash -lc {shlex.quote(script)}"

    def _clear_output(self) -> None:
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state=tk.DISABLED)

    def _append_output(self, text: str) -> None:
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.configure(state=tk.DISABLED)

    def _drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self.message_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "text":
                self._append_output(str(payload))
            elif kind == "done":
                result = dict(payload)
                title = str(result["title"])
                is_error = bool(result["is_error"])
                exit_code = result["exit_code"]
                if is_error:
                    self._set_busy(False, f"{title} finished with errors.")
                else:
                    self._set_busy(False, f"{title} finished successfully.")
                if exit_code is None:
                    self._append_output("\nAction ended due to an error before a remote exit code was available.\n")

        self.root.after(100, self._drain_queue)

    def _on_close(self) -> None:
        self._save_config(announce=False)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = BotManagerApp(root)
    app._append_output(
        "Local GUI ready. Recommended auth mode: SSH key.\n"
        "Use 'Update + sync deps' only when remote requirements.txt changed.\n"
    )
    root.mainloop()


if __name__ == "__main__":
    main()
