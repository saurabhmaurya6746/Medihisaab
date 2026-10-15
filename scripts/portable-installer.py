"""Small Windows installer for the portable MediHisaab release."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from zipfile import ZipFile


APP_VERSION = "1.0.7"
PACKAGE_NAME = "MediHisaab-v1.0.7-Portable.zip"


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
        programs_dir = local_app_data / "Programs"
        default_install = None

        # Check existing Desktop shortcut target/working directory first
        desktop_shortcut = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "MediHisaab.lnk"
        if desktop_shortcut.is_file():
            try:
                cmd = (
                    f"$s = New-Object -ComObject WScript.Shell; "
                    f"$l = $s.CreateShortcut({ps_quote(str(desktop_shortcut))}); "
                    f"Write-Output $l.WorkingDirectory; Write-Output $l.TargetPath"
                )
                res = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                for line in res.stdout.splitlines():
                    p = Path(line.strip())
                    if p.is_dir() and (p / "start-pharmacy.bat").is_file():
                        default_install = p
                        break
                    if p.is_file() and p.parent.is_dir() and (p.parent / "start-pharmacy.bat").is_file():
                        default_install = p.parent
                        break
            except Exception:
                pass

        if not default_install and programs_dir.exists():
            existing_with_launcher = sorted(
                (p for p in programs_dir.glob("MediHisaab*") if p.is_dir() and (p / "start-pharmacy.bat").is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if existing_with_launcher:
                default_install = existing_with_launcher[0]
            else:
                default_install = programs_dir / "MediHisaab"
        elif not default_install:
            default_install = programs_dir / "MediHisaab"

        self.install_dir = tk.StringVar(value=str(default_install))
        self.status = tk.StringVar(value="Install MediHisaab on this computer.")

        icon_candidate = resource_path("medihisaab-icon.ico")
        if not icon_candidate.is_file():
            icon_candidate = Path(__file__).resolve().parent.parent / "assets" / "medihisaab-icon.ico"
        if icon_candidate.is_file():
            try:
                self.root.iconbitmap(str(icon_candidate))
            except Exception:
                pass

        frame = ttk.Frame(self.root, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MediHisaab", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Version {APP_VERSION} • Update and startup fixes included").pack(anchor="w", pady=(2, 14))
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

        if not self.stop_running_app(destination):
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

    def stop_running_app(self, destination: Path) -> bool:
        """Ask before stopping a running MediHisaab process that locks update files."""
        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -in @('pharmacy-daemon.exe','desktop-window.exe') "
            "-and $_.ExecutablePath } | "
            "Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            import json

            rows = json.loads(result.stdout) if result.stdout.strip() else []
            if isinstance(rows, dict):
                rows = [rows]
        except Exception as exc:
            messagebox.showerror(
                "Could not check MediHisaab",
                f"The installer could not check whether MediHisaab is running. Close it and retry.\n\n{exc}",
                parent=self.root,
            )
            return False

        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        programs_dir = local_app_data / "Programs"
        processes = []
        for row in rows:
            executable = Path(row.get("ExecutablePath") or "")
            try:
                resolved = executable.resolve()
                in_destination = resolved.is_relative_to(destination.resolve())
                in_medi_hisaab_install = (
                    resolved.is_relative_to(programs_dir.resolve())
                    and any(part.casefold().startswith("medihisaab") for part in resolved.parts)
                )
                if in_destination or in_medi_hisaab_install:
                    processes.append(row)
            except (OSError, ValueError):
                continue

        if not processes:
            return True

        names = ", ".join(sorted({row.get("Name", "MediHisaab") for row in processes}))
        if not messagebox.askyesno(
            "MediHisaab is running",
            f"MediHisaab is still running ({names}). Finish or save any billing work first.\n\n"
            "Close MediHisaab now and continue the update? Your pharmacy data will be kept.",
            parent=self.root,
        ):
            return False

        # Close the UI first, then stop the local service so Windows releases files.
        processes.sort(key=lambda row: 0 if row.get("Name", "").casefold() == "desktop-window.exe" else 1)
        for row in processes:
            pid = str(int(row["ProcessId"]))
            try:
                subprocess.run(
                    ["taskkill.exe", "/PID", pid, "/T", "/F"],
                    check=True,
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.CalledProcessError as exc:
                messagebox.showerror(
                    "Could not close MediHisaab",
                    "Windows could not close the running app. Close MediHisaab manually in Task Manager, then retry.\n\n"
                    f"{exc.stderr.strip() or exc}",
                    parent=self.root,
                )
                return False

        time.sleep(1)
        return True

    def create_shortcut(self, destination: Path) -> None:
        desktop_shortcut = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "MediHisaab.lnk"
        start_menu_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "MediHisaab"
        start_menu_dir.mkdir(parents=True, exist_ok=True)
        start_menu_shortcut = start_menu_dir / "MediHisaab.lnk"
        start_menu_troubleshoot = start_menu_dir / "MediHisaab (Troubleshooting).lnk"

        launcher = destination / "start-pharmacy-hidden.vbs"
        bat_launcher = destination / "start-pharmacy.bat"
        wscript = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "wscript.exe"
        icon = destination / "medihisaab-icon.ico"

        script = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$link = $shell.CreateShortcut({ps_quote(str(desktop_shortcut))}); "
            f"$link.TargetPath = {ps_quote(str(wscript))}; "
            f"$link.Arguments = {ps_quote('\"' + str(launcher) + '\"')}; "
            f"$link.WorkingDirectory = {ps_quote(str(destination))}; "
            f"$link.IconLocation = {ps_quote(str(icon) + ',0')}; "
            "$link.Description = 'MediHisaab Offline Pharmacy Management'; "
            "$link.WindowStyle = 1; $link.Save(); "
            f"$smLink = $shell.CreateShortcut({ps_quote(str(start_menu_shortcut))}); "
            f"$smLink.TargetPath = {ps_quote(str(wscript))}; "
            f"$smLink.Arguments = {ps_quote('\"' + str(launcher) + '\"')}; "
            f"$smLink.WorkingDirectory = {ps_quote(str(destination))}; "
            f"$smLink.IconLocation = {ps_quote(str(icon) + ',0')}; "
            "$smLink.Description = 'MediHisaab Offline Pharmacy Management'; "
            "$smLink.WindowStyle = 1; $smLink.Save(); "
            f"$diagLink = $shell.CreateShortcut({ps_quote(str(start_menu_troubleshoot))}); "
            f"$diagLink.TargetPath = {ps_quote(str(bat_launcher))}; "
            f"$diagLink.WorkingDirectory = {ps_quote(str(destination))}; "
            f"$diagLink.IconLocation = {ps_quote(str(icon) + ',0')}; "
            "$diagLink.Description = 'MediHisaab Troubleshooting Launcher (Console Visible)'; "
            "$diagLink.WindowStyle = 1; $diagLink.Save()"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def open_app(self) -> None:
        destination = Path(self.install_dir.get()).expanduser()
        launcher = destination / "start-pharmacy-hidden.vbs"
        wscript = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "wscript.exe"
        subprocess.Popen(
            [str(wscript), str(launcher)],
            cwd=destination,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Installer().run()
