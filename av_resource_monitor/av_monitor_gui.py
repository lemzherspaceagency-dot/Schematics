#!/usr/bin/env python3
"""
Point-and-click GUI for monitoring the AGENT_665956_V10_15_3_RW EDR/AV
agent's CPU/RAM usage - no terminal, no typing process names.

How to use:
  1. Launch this before installing the agent (python av_monitor_gui.py).
  2. Install / start the agent as normal.
  3. Click "Refresh" in the app - any process that appeared since the app
     opened is tagged NEW and highlighted, so you don't have to guess
     which one is the agent.
  4. Tick the checkbox next to the process(es) to watch (a service, a
     tray icon, a scan engine can all be separate processes - tick all
     that look related), pick an output file, click Start.
  5. Watch the live numbers/graph, click Stop whenever. The JSON file is
     kept up to date the whole time and gets a summary block at the end.

Requires: psutil  (pip install psutil)
"""

import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import psutil
except ImportError:
    print("psutil is required but not installed.\nInstall it with:  pip install psutil")
    sys.exit(1)

import av_monitor_core as core

CHECK_ON = "☑"   # ☑
CHECK_OFF = "☐"  # ☐


class Graph(tk.Canvas):
    """Minimal dependency-free sparkline: two auto-scaled lines (CPU, RAM)."""

    def __init__(self, master, width=460, height=120, max_points=150, **kw):
        super().__init__(master, width=width, height=height, bg="#0f1115",
                          highlightthickness=0, **kw)
        self.width = width
        self.height = height
        self.max_points = max_points
        self.cpu_history = []
        self.ram_history = []

    def add_point(self, cpu, ram):
        self.cpu_history.append(cpu)
        self.ram_history.append(ram)
        self.cpu_history = self.cpu_history[-self.max_points:]
        self.ram_history = self.ram_history[-self.max_points:]
        self.redraw()

    def _plot(self, values, color, scale_max):
        if len(values) < 2 or scale_max <= 0:
            return
        n = len(values)
        step_x = self.width / max(self.max_points - 1, 1)
        x0 = self.width - (n - 1) * step_x
        points = []
        for i, v in enumerate(values):
            x = x0 + i * step_x
            y = self.height - (v / scale_max) * (self.height - 10) - 5
            points.extend([x, y])
        self.create_line(*points, fill=color, width=2, smooth=True)

    def redraw(self):
        self.delete("all")
        cpu_max = max(self.cpu_history + [1])
        ram_max = max(self.ram_history + [1])
        self._plot(self.cpu_history, "#4fc3f7", cpu_max)
        self._plot(self.ram_history, "#81c784", ram_max)
        self.create_text(6, 8, anchor="w", fill="#4fc3f7",
                          text=f"CPU% (max {cpu_max:.0f})", font=("TkDefaultFont", 8))
        self.create_text(6, 20, anchor="w", fill="#81c784",
                          text=f"RAM MB (max {ram_max:.0f})", font=("TkDefaultFont", 8))


class App:
    def __init__(self, root):
        self.root = root
        root.title("AV/EDR resursų monitorius")
        root.geometry("880x640")

        self.baseline_names = {p.info["name"] for p in psutil.process_iter(["name"])
                                if p.info["name"]}
        self.selected_pids = set()
        self.procs = []
        self.samples = []
        self.after_id = None
        self.start_time = None

        self._build_widgets()
        self.refresh_processes()

    # ---------------------------------------------------------------- UI

    def _build_widgets(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="both", expand=True)

        # --- process picker -------------------------------------------------
        picker_frame = ttk.LabelFrame(top, text="1) Pasirink programą / procesą", padding=6)
        picker_frame.pack(fill="both", expand=True)

        search_row = ttk.Frame(picker_frame)
        search_row.pack(fill="x", pady=(0, 4))
        ttk.Label(search_row, text="Paieška:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.render_tree())
        ttk.Entry(search_row, textvariable=self.search_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(search_row, text="Refresh", command=self.refresh_processes).pack(side="left")

        tree_area = ttk.Frame(picker_frame)
        tree_area.pack(fill="both", expand=True)
        tree_area.columnconfigure(0, weight=1)
        tree_area.rowconfigure(0, weight=1)

        columns = ("sel", "pid", "name", "exe", "status")
        self.tree = ttk.Treeview(tree_area, columns=columns, show="headings", height=12)
        for col, label, w in [("sel", "", 36), ("pid", "PID", 70), ("name", "Vardas", 180),
                               ("exe", "Kelias", 380), ("status", "Būsena", 70)]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor="w", stretch=(col == "exe"))
        self.tree.tag_configure("new", background="#fff3b0")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self.on_tree_click)

        scroll = ttk.Scrollbar(tree_area, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        hint = ttk.Label(picker_frame,
                          text="Pageltonintos eilutės = nauji procesai nuo šios programėlės paleidimo "
                               "(paspausk Refresh po agento diegimo). Spausk eilutę, kad pažymėtum.",
                          foreground="#666")
        hint.pack(fill="x", pady=(4, 0), side="bottom")

        # --- settings ---------------------------------------------------
        settings = ttk.LabelFrame(top, text="2) Nustatymai", padding=6)
        settings.pack(fill="x", pady=8)

        ttk.Label(settings, text="Intervalas (s):").grid(row=0, column=0, sticky="w")
        self.interval_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(settings, from_=0.5, to=60, increment=0.5, textvariable=self.interval_var,
                    width=6).grid(row=0, column=1, sticky="w", padx=(4, 16))

        ttk.Label(settings, text="Trukmė (s, 0 = kol paspausi Stop):").grid(row=0, column=2, sticky="w")
        self.duration_var = tk.IntVar(value=0)
        ttk.Spinbox(settings, from_=0, to=999999, increment=10, textvariable=self.duration_var,
                    width=8).grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(settings, text="Išvesties JSON:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.output_var = tk.StringVar(value="av_resource_usage.json")
        ttk.Entry(settings, textvariable=self.output_var, width=50).grid(
            row=1, column=1, columnspan=2, sticky="we", pady=(6, 0), padx=4)
        ttk.Button(settings, text="Browse...", command=self.browse_output).grid(
            row=1, column=3, sticky="w", pady=(6, 0))
        settings.columnconfigure(1, weight=1)

        # --- controls -----------------------------------------------------
        controls = ttk.Frame(top)
        controls.pack(fill="x", pady=(0, 8))
        self.start_btn = ttk.Button(controls, text="▶ Start", command=self.start_monitoring)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(controls, text="■ Stop", command=self.stop_monitoring, state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        self.status_var = tk.StringVar(value="Nepaleista.")
        ttk.Label(controls, textvariable=self.status_var).pack(side="left", padx=12)

        # --- live view ------------------------------------------------
        live = ttk.LabelFrame(top, text="3) Gyvi duomenys", padding=6)
        live.pack(fill="both", expand=True)

        live_cols = ("name", "pid", "cpu", "ram")
        self.live_tree = ttk.Treeview(live, columns=live_cols, show="headings", height=6)
        for col, label, w in [("name", "Vardas", 160), ("pid", "PID", 70),
                               ("cpu", "CPU %", 90), ("ram", "RAM MB", 100)]:
            self.live_tree.heading(col, text=label)
            self.live_tree.column(col, width=w, anchor="w")
        self.live_tree.pack(fill="x")

        self.totals_var = tk.StringVar(value="")
        ttk.Label(live, textvariable=self.totals_var, font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", pady=(6, 4))

        self.graph = Graph(live)
        self.graph.pack(fill="x", pady=(4, 0))

    # ------------------------------------------------------------- process list

    def refresh_processes(self):
        self.processes = []
        for p in psutil.process_iter(["pid", "name", "exe"]):
            try:
                self.processes.append({
                    "pid": p.pid,
                    "name": p.info["name"] or "",
                    "exe": p.info["exe"] or "",
                    "new": (p.info["name"] or "") not in self.baseline_names,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.processes.sort(key=lambda d: (not d["new"], d["name"].lower()))
        self.render_tree()

    def render_tree(self):
        query = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        for proc in self.processes:
            if query and query not in proc["name"].lower() and query not in proc["exe"].lower():
                continue
            sel = CHECK_ON if proc["pid"] in self.selected_pids else CHECK_OFF
            status = "NAUJAS" if proc["new"] else ""
            tags = ("new",) if proc["new"] else ()
            self.tree.insert("", "end", iid=str(proc["pid"]),
                              values=(sel, proc["pid"], proc["name"], proc["exe"], status),
                              tags=tags)

    def on_tree_click(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col != "#1":  # only the checkbox column toggles selection
            return
        pid = int(row)
        if pid in self.selected_pids:
            self.selected_pids.discard(pid)
        else:
            self.selected_pids.add(pid)
        self.render_tree()

    def browse_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                             initialfile="av_resource_usage.json",
                                             filetypes=[("JSON", "*.json")])
        if path:
            self.output_var.set(path)

    # ------------------------------------------------------------- monitoring

    def start_monitoring(self):
        if not self.selected_pids:
            messagebox.showwarning("Nepasirinkta", "Pažymėk bent vieną procesą sąraše.")
            return

        procs = []
        for pid in self.selected_pids:
            try:
                procs.append(psutil.Process(pid))
            except psutil.NoSuchProcess:
                continue
        if not procs:
            messagebox.showerror("Klaida", "Pasirinkti procesai nebeegzistuoja - pasidaryk Refresh.")
            return

        self.procs = procs
        core.prime(self.procs)
        self.samples = []
        self.start_time = time.monotonic()
        self.graph.cpu_history.clear()
        self.graph.ram_history.clear()

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Stebima...")
        self.tick()

    def tick(self):
        interval = float(self.interval_var.get())
        duration = float(self.duration_var.get())

        per_proc, aggregate, alive = core.sample(self.procs)
        self.procs = alive
        sys_cpu = psutil.cpu_percent(interval=None)
        sys_mem = psutil.virtual_memory()
        logical_cpus = psutil.cpu_count(logical=True) or 1

        entry = {
            "timestamp": core.now_iso(),
            "elapsed_s": round(time.monotonic() - self.start_time, 1),
            "target": {
                "processes": per_proc,
                **aggregate,
                "cpu_percent_of_all_cores": round(aggregate["cpu_percent_sum"] / logical_cpus, 2),
            },
            "system": {
                "cpu_percent": sys_cpu,
                "ram_used_percent": sys_mem.percent,
                "ram_used_mb": round((sys_mem.total - sys_mem.available) / (1024 * 1024), 2),
                "ram_total_mb": round(sys_mem.total / (1024 * 1024), 2),
            },
        }
        self.samples.append(entry)

        core.atomic_write_json(self.output_var.get(), {
            "target_pids": list(self.selected_pids),
            "interval_s": interval,
            "logical_cpus": logical_cpus,
            "samples": self.samples,
        })

        self.update_live_view(per_proc, aggregate, entry["system"])
        self.graph.add_point(aggregate["cpu_percent_sum"], aggregate["rss_mb_sum"])

        if not self.procs:
            self.status_var.set("Visi stebėti procesai baigė darbą.")
            self.stop_monitoring()
            return

        if duration and entry["elapsed_s"] >= duration:
            self.stop_monitoring()
            return

        self.after_id = self.root.after(int(interval * 1000), self.tick)

    def update_live_view(self, per_proc, aggregate, system):
        self.live_tree.delete(*self.live_tree.get_children())
        for proc in per_proc:
            self.live_tree.insert("", "end", values=(
                proc["name"], proc["pid"], f"{proc['cpu_percent']:.1f}", f"{proc['rss_mb']:.1f}"))
        self.totals_var.set(
            f"Iš viso: CPU {aggregate['cpu_percent_sum']:.1f}%  |  RAM {aggregate['rss_mb_sum']:.1f} MB   "
            f"—   Sistema: CPU {system['cpu_percent']:.1f}%  RAM {system['ram_used_percent']:.1f}%"
        )

    def stop_monitoring(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.samples:
            summary = core.build_summary(self.samples)
            core.atomic_write_json(self.output_var.get(), {
                "target_pids": list(self.selected_pids),
                "interval_s": float(self.interval_var.get()),
                "logical_cpus": psutil.cpu_count(logical=True),
                "summary": summary,
                "samples": self.samples,
            })
            self.status_var.set(
                f"Sustabdyta. CPU vid={summary['cpu_percent_sum']['avg']}% max={summary['cpu_percent_sum']['max']}% | "
                f"RAM vid={summary['ram_mb_sum']['avg']}MB max={summary['ram_mb_sum']['max']}MB "
                f"({summary['sample_count']} matavimų) → {self.output_var.get()}"
            )
        else:
            self.status_var.set("Sustabdyta (duomenų nesurinkta).")

        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def on_close(self):
        self.stop_monitoring()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
