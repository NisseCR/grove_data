"""
Tkinter UI for the asset pipeline. Run via run.bat at the project root.
"""

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

SCRIPTS_DIR = Path(__file__).parent

BG        = "#111111"
BG_OUT    = "#0a0a0a"
BG_BTN    = "#1e1e1e"
FG        = "#999999"
FG_DIM    = "#555555"
FG_ERR    = "#f87171"
FG_WARN   = "#fbbf24"
FG_OK     = "#4ade80"
FONT      = ("Consolas", 11)
FONT_SM   = ("Consolas", 10)


class PipelineUI:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Asset Pipeline")
        self.root.configure(bg=BG)
        self.root.geometry("720x480")
        self.root.minsize(480, 320)

        self._q: queue.Queue = queue.Queue()
        self._build()
        self._poll()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Construct all widgets."""
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "P.TButton",
            background=BG_BTN, foreground="#bbbbbb",
            bordercolor="#2e2e2e", lightcolor=BG_BTN, darkcolor=BG_BTN,
            focusthickness=0, relief="flat", padding=(14, 5),
            font=FONT,
        )
        style.map(
            "P.TButton",
            background=[("active", "#272727"), ("disabled", "#161616")],
            foreground=[("disabled", "#444444")],
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#1e1e1e", troughcolor=BG_OUT,
            arrowcolor="#444444", bordercolor=BG_OUT,
        )

        bar = tk.Frame(self.root, bg=BG, padx=12, pady=10)
        bar.pack(fill="x")

        self._buttons: dict[str, ttk.Button] = {}
        for cmd in ("kebab", "preprocess", "sync"):
            btn = ttk.Button(
                bar, text=cmd.capitalize(), style="P.TButton",
                command=lambda c=cmd: self._run(c),
            )
            btn.pack(side="left", padx=(0, 6))
            self._buttons[cmd] = btn

        ttk.Button(bar, text="Clear", style="P.TButton", command=self._clear).pack(side="right")

        self._status_var = tk.StringVar()
        self._status_lbl = tk.Label(
            self.root, textvariable=self._status_var,
            bg=BG, fg=FG_DIM, font=FONT_SM, anchor="w", padx=14,
        )
        self._status_lbl.pack(fill="x")

        out_frame = tk.Frame(self.root, bg=BG_OUT, padx=12, pady=10)
        out_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self._out = tk.Text(
            out_frame,
            bg=BG_OUT, fg=FG, font=FONT,
            relief="flat", state="disabled", wrap="word",
            insertbackground=BG_OUT, selectbackground="#222222",
            borderwidth=0,
        )
        self._out.tag_configure("err",  foreground=FG_ERR)
        self._out.tag_configure("warn", foreground=FG_WARN)
        self._out.tag_configure("ok",   foreground=FG_OK)

        sb = ttk.Scrollbar(out_frame, orient="vertical", command=self._out.yview)
        self._out.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._out.pack(side="left", fill="both", expand=True)

    # ── Queue polling ─────────────────────────────────────────────────────────

    def _poll(self) -> None:
        """Drain the thread-safe queue on the main thread every 50 ms."""
        try:
            while True:
                line, tag = self._q.get_nowait()
                self._append(line, tag)
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    # ── Output helpers ────────────────────────────────────────────────────────

    def _append(self, text: str, tag: str) -> None:
        self._out.configure(state="normal")
        self._out.insert("end", text + "\n", tag or ())
        self._out.see("end")
        self._out.configure(state="disabled")

    def _clear(self) -> None:
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.configure(state="disabled")
        self._status_var.set("")
        self._status_lbl.configure(fg=FG_DIM)

    def _set_status(self, text: str, color: str) -> None:
        self._status_var.set(text)
        self._status_lbl.configure(fg=color)

    # ── Command execution ─────────────────────────────────────────────────────

    def _run(self, command: str) -> None:
        """Clear output, disable buttons, and spawn the command in a thread."""
        self._clear()
        for btn in self._buttons.values():
            btn.configure(state="disabled")
        self._set_status(f"Running {command}…", "#888888")
        threading.Thread(target=self._worker, args=(command,), daemon=True).start()

    def _worker(self, command: str) -> None:
        """Run the pipeline command and stream output into the queue."""
        try:
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / "main.py"), command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(SCRIPTS_DIR),
            )
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                self._q.put((line, self._classify(line)))
            proc.wait()

            if proc.returncode == 0:
                self.root.after(0, lambda: self._set_status("Done ✓", FG_OK))
            else:
                code = proc.returncode
                self.root.after(0, lambda: self._set_status(f"Failed (exit {code})", FG_ERR))
        except Exception as exc:
            self._q.put((f"[error] {exc}", "err"))
            self.root.after(0, lambda: self._set_status("Error", FG_ERR))
        finally:
            self.root.after(0, self._enable_buttons)

    def _enable_buttons(self) -> None:
        for btn in self._buttons.values():
            btn.configure(state="normal")

    @staticmethod
    def _classify(line: str) -> str:
        """Return a text tag based on line content."""
        t = line.lower()
        if "error" in t or line.startswith("Traceback"):
            return "err"
        if "warn" in t:
            return "warn"
        if "done" in t or "complete" in t or "✓" in line:
            return "ok"
        return ""

    def start(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    PipelineUI().start()
