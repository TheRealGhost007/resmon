"""A live-refreshing process table: Apps (collapsible process trees) vs.
System (everything else, flat), with kill.

"Apps" isn't just the literal window-owning process — it's that process's
whole descendant tree, collapsed under it by default with a disclosure
arrow to expand, so a browser's renderer/GPU helper subprocesses land under
the browser instead of cluttering System as unlabeled generic entries. The
collapsed parent row shows the *aggregate* CPU/memory across its whole
subtree, since the window-owning process alone is often nearly idle while
its children do the real work.
"""

from __future__ import annotations

import json
import subprocess
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango

from .process_classify import belongs_to_app, subtree_totals

import psutil

PROCESS_LIMIT = 100


class ProcessEntry(GObject.Object):
    __gtype_name__ = "ResmonProcessEntry"

    def __init__(self, pid: int, ppid: int, name: str, cpu: float, mem: float):
        super().__init__()
        self.pid = pid
        self.ppid = ppid
        self.name = name
        self.cpu = cpu
        self.mem = mem


def _running_app_titles() -> dict[int, str]:
    """PID -> window title, for processes that own a Hyprland window."""
    try:
        out = subprocess.run(
            ["hyprctl", "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=1,
            check=True,
        )
        clients = json.loads(out.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}

    titles: dict[int, str] = {}
    for client in clients:
        pid = client.get("pid", -1)
        if pid > 0:
            titles[pid] = client.get("title") or client.get("class") or ""
    return titles


def _identity(item):
    return item


def _from_tree_row(row: Gtk.TreeListRow) -> ProcessEntry:
    return row.get_item()


def _text_column(
    title: str,
    xalign: float,
    expand: bool,
    get_text: Callable[[ProcessEntry], str],
    unwrap: Callable = _identity,
) -> Gtk.ColumnViewColumn:
    factory = Gtk.SignalListItemFactory()

    def on_setup(_factory, item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=xalign)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        label.set_margin_start(10)
        label.set_margin_end(10)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        item.set_child(label)

    def on_bind(_factory, item: Gtk.ListItem) -> None:
        item.get_child().set_label(get_text(unwrap(item.get_item())))

    factory.connect("setup", on_setup)
    factory.connect("bind", on_bind)
    column = Gtk.ColumnViewColumn(title=title, factory=factory)
    column.set_expand(expand)
    return column


def _name_expander_column() -> Gtk.ColumnViewColumn:
    """The Apps table's Name column: an expand arrow + indentation per depth,
    built into Gtk.TreeExpander — collapsed by default, click to reveal
    children."""
    factory = Gtk.SignalListItemFactory()

    def on_setup(_factory, item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        expander = Gtk.TreeExpander()
        expander.set_child(label)
        item.set_child(expander)

    def on_bind(_factory, item: Gtk.ListItem) -> None:
        tree_row: Gtk.TreeListRow = item.get_item()
        expander: Gtk.TreeExpander = item.get_child()
        expander.set_list_row(tree_row)
        expander.get_child().set_label(tree_row.get_item().name)

    factory.connect("setup", on_setup)
    factory.connect("bind", on_bind)
    column = Gtk.ColumnViewColumn(title="Name", factory=factory)
    column.set_expand(True)
    return column


def _kill_column(on_kill: Callable[[ProcessEntry], None], unwrap: Callable = _identity) -> Gtk.ColumnViewColumn:
    factory = Gtk.SignalListItemFactory()

    def on_setup(_factory, item: Gtk.ListItem) -> None:
        button = Gtk.Button(icon_name="window-close-symbolic", tooltip_text="End Process")
        button.add_css_class("flat")
        button.add_css_class("circular")
        item.set_child(button)

    def on_bind(_factory, item: Gtk.ListItem) -> None:
        button: Gtk.Button = item.get_child()
        entry = unwrap(item.get_item())
        handler_id = getattr(button, "_resmon_handler_id", None)
        if handler_id is not None:
            button.disconnect(handler_id)
        button._resmon_handler_id = button.connect("clicked", lambda _b: on_kill(entry))

    factory.connect("setup", on_setup)
    factory.connect("bind", on_bind)
    column = Gtk.ColumnViewColumn(title="", factory=factory)
    column.set_fixed_width(48)
    return column


class _ProcessTable(Gtk.ScrolledWindow):
    """A killable process table — flat, or a collapsible tree."""

    def __init__(self, on_kill: Callable[[ProcessEntry], None], *, onyx: bool = False, tree: bool = False):
        super().__init__()
        self.set_vexpand(True)
        self.add_css_class("card")
        if onyx:
            self.add_css_class("onyx-surface")

        self._tree = tree
        self._children_of: dict[int, list[ProcessEntry]] = {}

        self._view = Gtk.ColumnView()
        if tree:
            self._view.append_column(_name_expander_column())
            self._view.append_column(_text_column("PID", 1.0, False, lambda e: str(e.pid), unwrap=_from_tree_row))
            self._view.append_column(_text_column("CPU %", 1.0, False, lambda e: f"{e.cpu:.1f}", unwrap=_from_tree_row))
            self._view.append_column(
                _text_column("Memory %", 1.0, False, lambda e: f"{e.mem:.1f}", unwrap=_from_tree_row)
            )
            self._view.append_column(_kill_column(on_kill, unwrap=_from_tree_row))
            self.set_tree_entries([], {})
        else:
            self._store = Gio.ListStore(item_type=ProcessEntry)
            self._view.set_model(Gtk.NoSelection(model=self._store))
            self._view.append_column(_text_column("PID", 0.0, False, lambda e: str(e.pid)))
            self._view.append_column(_text_column("Name", 0.0, True, lambda e: e.name))
            self._view.append_column(_text_column("CPU %", 1.0, False, lambda e: f"{e.cpu:.1f}"))
            self._view.append_column(_text_column("Memory %", 1.0, False, lambda e: f"{e.mem:.1f}"))
            self._view.append_column(_kill_column(on_kill))

        self.set_child(self._view)

    def _create_child_model(self, entry: ProcessEntry) -> Gio.ListModel | None:
        kids = self._children_of.get(entry.pid)
        if not kids:
            return None
        store = Gio.ListStore(item_type=ProcessEntry)
        for kid in kids:
            store.append(kid)
        return store

    def set_entries(self, entries: list[ProcessEntry]) -> None:
        self._store.remove_all()
        for entry in entries:
            self._store.append(entry)

    def set_tree_entries(self, roots: list[ProcessEntry], children_of: dict[int, list[ProcessEntry]]) -> None:
        # Rebuilt fresh each call rather than mutated in place, so expanded
        # branches never show stale data — the tradeoff is expand state
        # resets on each refresh, same as everything else in this app.
        self._children_of = children_of
        root_store = Gio.ListStore(item_type=ProcessEntry)
        for root in roots:
            root_store.append(root)
        tree_model = Gtk.TreeListModel.new(root_store, False, False, self._create_child_model)
        self._view.set_model(Gtk.NoSelection(model=tree_model))


class ProcessListView(Gtk.Box):
    def __init__(self, *, onyx: bool = False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._search_entry = Gtk.SearchEntry(placeholder_text="Search processes…")
        self._search_entry.connect("search-changed", lambda _e: self.refresh())
        self.append(self._search_entry)

        toggle_box = Gtk.Box()
        toggle_box.add_css_class("linked")
        toggle_box.set_halign(Gtk.Align.CENTER)

        self._apps_btn = Gtk.ToggleButton(label="Apps", active=True)
        self._processes_btn = Gtk.ToggleButton(label="System")
        self._processes_btn.set_group(self._apps_btn)
        self._apps_btn.connect("toggled", self._on_mode_toggled)
        toggle_box.append(self._apps_btn)
        toggle_box.append(self._processes_btn)
        self.append(toggle_box)

        self._apps_table = _ProcessTable(self._confirm_kill, onyx=onyx, tree=True)
        self._processes_table = _ProcessTable(self._confirm_kill, onyx=onyx)
        self._processes_table.set_visible(False)
        self.append(self._apps_table)
        self.append(self._processes_table)

    def _on_mode_toggled(self, _button: Gtk.ToggleButton) -> None:
        showing_apps = self._apps_btn.get_active()
        self._apps_table.set_visible(showing_apps)
        self._processes_table.set_visible(not showing_apps)

    def refresh(self) -> None:
        query = self._search_entry.get_text().strip().lower()
        app_titles = _running_app_titles()

        entries: list[ProcessEntry] = []
        ppid_of: dict[int, int] = {}
        for proc in psutil.process_iter(["pid", "ppid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            pid = info["pid"]
            ppid = info.get("ppid") or 0
            ppid_of[pid] = ppid
            name = app_titles.get(pid) or info.get("name") or "?"
            entries.append(ProcessEntry(pid, ppid, name, info.get("cpu_percent") or 0.0, info.get("memory_percent") or 0.0))

        entries.sort(key=lambda e: e.cpu, reverse=True)

        app_roots = set(app_titles)
        membership_cache: dict[int, bool] = {}

        app_entries: list[ProcessEntry] = []
        system_entries: list[ProcessEntry] = []
        for entry in entries:
            is_app = belongs_to_app(entry.pid, ppid_of, app_roots, membership_cache)
            (app_entries if is_app else system_entries).append(entry)

        # Direct-children index for the tree. Roots are excluded here (their
        # OS-level parent is usually a shell/session process we don't show,
        # not another app) so they land as top-level tree items instead of
        # nested under nothing.
        children_of: dict[int, list[ProcessEntry]] = {}
        for entry in app_entries:
            if entry.pid not in app_roots:
                children_of.setdefault(entry.ppid, []).append(entry)

        roots = []
        for entry in app_entries:
            if entry.pid in app_roots:
                total_cpu, total_mem = subtree_totals(entry.pid, children_of, entry.cpu, entry.mem)
                roots.append(ProcessEntry(entry.pid, entry.ppid, entry.name, total_cpu, total_mem))
        roots.sort(key=lambda e: e.cpu, reverse=True)

        if query:
            system_entries = [e for e in system_entries if query in e.name.lower()]

            def subtree_matches(entry: ProcessEntry) -> bool:
                if query in entry.name.lower():
                    return True
                return any(subtree_matches(child) for child in children_of.get(entry.pid, []))

            roots = [r for r in roots if subtree_matches(r)]

        self._apps_table.set_tree_entries(roots[:PROCESS_LIMIT], children_of)
        self._processes_table.set_entries(system_entries[:PROCESS_LIMIT])

    def _confirm_kill(self, entry: ProcessEntry) -> None:
        dialog = Adw.AlertDialog(
            heading=f"End “{entry.name}”?",
            body=f"This will terminate process {entry.pid}. Unsaved work in it may be lost.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("end", "End Process")
        dialog.set_response_appearance("end", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_kill_response, entry)
        dialog.present(self)

    def _on_kill_response(self, _dialog: Adw.AlertDialog, response: str, entry: ProcessEntry) -> None:
        if response != "end":
            return
        try:
            psutil.Process(entry.pid).terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        GLib.timeout_add(300, self._refresh_once)

    def _refresh_once(self) -> bool:
        self.refresh()
        return GLib.SOURCE_REMOVE
