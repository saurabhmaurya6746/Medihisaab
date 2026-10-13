"""Small Windows installer for the portable MediHisaab release."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from zipfile import ZipFile


APP_VERSION = "1.0.2"
PACKAGE_NAME = "MediHisaab-v1.0.1-Portable.zip"


def resource_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Installer:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"MediHisaab Setup {APP_VERSION}")
        self.root.geometry("560x330")
        self.root.resizable(False, False)

        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        self.install_dir = tk.StringVar(
            value=str(local_app_data / "Programs" / f"MediHisaab-{APP_VERSION}")
        )
        self.status = tk.StringVar(value="Install MediHisaab on this computer.")

        frame = ttk.Frame(self.root, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MediHisaab", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Version {APP_VERSION} • License import fix included").pack(anchor="w", pady=(2, 14))
        ttk.Label(frame, text="Install location").pack(anchor="w")

        path_row = ttk.Frame(frame)
        path_row.pack(fill="x", pady=(4, 12))
        ttk.Entry(path_row, textvariable=self.install_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Browse…", command=self.choose_folder).pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 6))
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        self.open_button = ttk.Button(buttons, text="Open MediHisaab", command=self.open_app, state="disabled")
        self.open_button.pack(side="right")
        self.install_button = ttk.Button(buttons, text="Install", command=self.install)
        self.install_button.pack(side="right", padx=(0, 8))

    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(
            parent=self.root,
            title="Choose the MediHisaab install folder",
            initialdir=self.install_dir.get(),
            mustexist=False,
        )
        if chosen:
            self.install_dir.set(chosen)

    def install(self) -> None:
        destination = Path(self.install_dir.get()).expanduser()
        if destination.exists() and any(destination.iterdir()):
            if not messagebox.askyesno(
                "Folder already exists",
                "MediHisaab files already exist in this folder. Update those files and keep your pharmacy data?",
                parent=self.root,
            ):
                return

        archive = resource_path(PACKAGE_NAME)
        if not archive.is_file():
            messagebox.showerror("Installer package missing", "The MediHisaab application files are missing from this setup.", parent=self.root)
            return

        self.install_button.configure(state="disabled")
        self.status.set("Preparing application files…")
        self.root.update_idletasks()

        try:
            destination.mkdir(parents=True, exist_ok=True)
            with ZipFile(archive) as package:
                files = [entry for entry in package.infolist() if not entry.is_dir()]
                self.progress.configure(maximum=max(1, len(files)), value=0)
                root = destination.resolve()
                for index, entry in enumerate(files, start=1):
                    target = (destination / entry.filename).resolve()
                    if not target.is_relative_to(root):
                        raise ValueError("The installer package contains an invalid file path.")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(entry) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    self.status.set(f"Installing {entry.filename}")
                    self.progress.configure(value=index)
                    self.root.update_idletasks()

            self.create_shortcut(destination)
            self.status.set("Installation complete. Your pharmacy data remains in its existing data folder.")
            self.open_button.configure(state="normal")
            messagebox.showinfo("Installation complete", "MediHisaab was installed successfully. Import your signed license file when the app opens.", parent=self.root)
        except Exception as exc:
            self.status.set("Installation did not complete.")
            self.install_button.configure(state="normal")
            messagebox.showerror("Installation failed", str(exc), parent=self.root)

    def create_shortcut(self, destination: Path) -> None:
        shortcut = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "MediHisaab.lnk"
        launcher = destination / "start-pharmacy.bat"
        script = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$link = $shell.CreateShortcut({ps_quote(str(shortcut))}); "
            f"$link.TargetPath = {ps_quote(str(launcher))}; "
            f"$link.WorkingDirectory = {ps_quote(str(destination))}; "
            "$link.WindowStyle = 7; $link.Save()"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def open_app(self) -> None:
        destination = Path(self.install_dir.get()).expanduser()
        launcher = destination / "start-pharmacy.bat"
        subprocess.Popen(["cmd.exe", "/c", str(launcher)], cwd=destination, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Installer().run()
