"""Contrôleur : relie backend, salles, moteur de placement et actions.

Un seul thread de travail possède l'état (moteur, tables) et traite une file
de tâches : balayages périodiques des fenêtres et actions déclenchées par les
raccourcis.  L'interface reçoit des événements via ``on_event``.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Hashable

from .backends.base import Backend, BackendError, WindowInfo
from .betsizing import BetContext, adjust_bet, compute_bet, format_amount
from .config import Config
from .geometry import Rect
from .hotkeys import TABLE_ACTIONS, Action
from .layout import SlotKind
from .placement import LOBBY, REPLAY, TABLE, Focus, Move, PlacementEngine, Raise, TableState
from .session import SessionTracker
from .sites import SiteDefinition, parse_stakes

log = logging.getLogger("fukuroku")

# Actions purement « interface » relayées à l'UI.
UI_ACTIONS = {Action.OpenMenu, Action.OpenNotificationsDebugWindow, Action.RNGMoveToPointer,
              Action.PeekActiveLayoutHotKey, Action.ResetMainWindowPosition, Action.ShowControllerCursor,
              Action.HideShowBoard, Action.ToggleBBMode}

CLICK_ACTIONS = {Action.Fold: "fold", Action.Check: "check", Action.BetRaise: "bet", Action.AllIn: "allin",
                 Action.Increment: "increase_bet", Action.Decrement: "decrease_bet",
                 Action.SitoutNextHand: "sitout_next_hand", Action.SitoutNextBB: "sitout_next_bb",
                 Action.SitBackIn: "sit_back_in"}
# Après ces clics, la table n'attend plus d'action.
ACTING_CLICKS = {Action.Fold, Action.Check, Action.BetRaise, Action.AllIn}
# Actions transmises au client par ses propres raccourcis (« Contournement des hotkeys »).
SITE_KEY_ACTIONS = {Action.Fold: "fold", Action.Check: "check", Action.BetRaise: "bet", Action.AllIn: "allin",
                    Action.Increment: "increment", Action.Decrement: "decrement", Action.IncreaseBet: "increment",
                    Action.DecreaseBet: "decrement", Action.ToggleBBMode: "toggle_bb",
                    Action.Button1: "button1", Action.Button2: "button2", Action.Button3: "button3",
                    Action.Button4: "button4"}
# Sans fournisseur de données, une table quitte le slot In Hand après ce délai sans action requise.
IN_HAND_IDLE_S = 25.0
# Deux demandes d'action espacées de plus de ce délai comptent comme deux mains (estimation).
NEW_HAND_GAP_S = 20.0


@dataclass
class TableDataSnapshot:
    """Données de main fournies par un fournisseur externe (optionnel)."""

    pot: float | None = None
    to_call: float = 0.0
    hero_stack: float | None = None
    street: str = "preflop"
    last_bet: float | None = None
    in_hand: bool | None = None


TableDataProvider = Callable[[Hashable, str], "TableDataSnapshot | None"]


class TableManager:
    def __init__(self, config: Config, backend: Backend, on_event: Callable[[str, dict], None] | None = None,
                 clock: Callable[[], float] = time.time):
        self.config = config
        self.backend = backend
        self.on_event = on_event or (lambda kind, data: None)
        self.clock = clock
        self.screens = self._safe(backend.screens, [Rect(0, 0, 1920, 1080)])
        config.ensure_layouts(self.screens)
        self.engine = PlacementEngine(config.layout(), config.placement)
        self.session = SessionTracker(break_every_min=config.general.break_every_min)
        self.data_provider: TableDataProvider | None = None
        self.ctrl_pressed: Callable[[], bool] = lambda: False
        self.bet_amounts: dict[Hashable, float] = {}
        self._expected: dict[Hashable, Rect] = {}
        self._pending_move: dict[Hashable, Rect] = {}
        self._last_windows: list[WindowInfo] = []
        self._last_focus: Hashable | None = None
        self._alarmed: set[Hashable] = set()
        self._last_ar_end: dict[Hashable, float] = {}
        self._layout_stack: list[str] = []
        self._pending_switch: str | None = None
        self.paused = False
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.lock = threading.RLock()
        if config.auto_switch.enabled and config.auto_switch.initial_layout and config.layout(config.auto_switch.initial_layout):
            config.active_layout = config.auto_switch.initial_layout
            self.engine.layout = config.layout()

    # ------------------------------------------------------------------ boucle
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="fukuroku-manager", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)

    def submit(self, fn: Callable, *args) -> None:
        self._queue.put((fn, args))

    def trigger(self, action: Action, arg=None) -> None:
        self.submit(self.perform, action, arg)

    def _run(self) -> None:
        next_scan = 0.0
        while not self._stop.is_set():
            timeout = max(0.0, next_scan - time.monotonic())
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                item = ("scan",)
            if item is None:
                break
            try:
                if item == ("scan",):
                    if not self.paused:
                        self.scan()
                    next_scan = time.monotonic() + self.config.general.poll_interval_ms / 1000
                else:
                    fn, args = item
                    fn(*args)
            except Exception as exc:  # le gestionnaire ne doit jamais s'arrêter
                log.exception("erreur du gestionnaire")
                self.on_event("error", {"message": str(exc)})

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception as exc:
            log.warning("backend : %s", exc)
            return default

    # ------------------------------------------------------------------ détection
    def classify(self, w: WindowInfo) -> tuple[SiteDefinition, str] | None:
        """Salle et rôle (table, lobby, replay) d'une fenêtre, ou None."""
        if w.title in self.config.ignored_titles:
            return None
        names = [w.process_name] + [p for p in w.class_name.split(".") if p]
        for site in self.config.sites:
            if not site.enabled:
                continue
            if site.processes and not any(site.matches_process(n) for n in names if n):
                continue
            if site.is_table(w.title, w.class_name, w.rect.w, w.rect.h):
                return site, TABLE
            if site.processes and site.is_lobby(w.title) and self.engine.layout.has(SlotKind.LOBBY):
                return site, LOBBY
            if site.processes and site.is_replay(w.title) and self.engine.layout.has(SlotKind.REPLAY):
                return site, REPLAY
        return None

    def identify(self, w: WindowInfo) -> SiteDefinition | None:
        found = self.classify(w)
        return found[0] if found and found[1] == TABLE else None

    def table_count(self) -> int:
        return len(self.engine.poker_tables())

    def scan(self) -> None:
        windows = self._safe(self.backend.list_windows, None)
        if windows is None:
            return
        with self.lock:
            self._last_windows = windows
            seen: set[Hashable] = set()
            now = self.clock()
            count_before = self.table_count()
            for w in windows:
                found = self.classify(w)
                if found is None:
                    continue
                site, role = found
                seen.add(w.handle)
                t = self.engine.tables.get(w.handle)
                if t is None:
                    self._open(w, site, role, now)
                    continue
                if w.title != t.title:
                    t.title = w.title
                    t.stakes = parse_stakes(w.title) or t.stakes
                t.minimized = w.minimized
                self._detect_user_move(t, w)
                if role == TABLE:
                    self._probe_action(t, w, site, now)
                    self._probe_data(t, now)
            for handle in [h for h in self.engine.tables if h not in seen]:
                self._close(handle, now)
            if self.table_count() != count_before:
                self._auto_switch(count_before, self.table_count())
            self._check_alarms(now)
            if self.config.general.focus_follows_mouse:
                self._focus_follows_mouse()
            self._session_tick(now)
        self.on_event("tables", {})

    def _open(self, w: WindowInfo, site: SiteDefinition, role: str, now: float) -> None:
        t = TableState(w.handle, site.id, w.title, w.rect, arrival=now, stakes=parse_stakes(w.title),
                       minimized=w.minimized, role=role)
        if role == TABLE:
            self.session.on_table_opened(auto_start=self.config.session.timer_enabled and
                                         self.config.session.start_mode == "first_table", now=now)
            if self.session.tables_goal_reached(self.config.session.notify_tables if
                                                self.config.session.notify_tables_enabled else 0):
                self.on_event("session_tables_goal", {"tables": self.session.tables_opened})
        cmds = self.engine.add_table(t, site.new_table) if site.tiling else self._register_only(t)
        self._apply(cmds)
        if role == TABLE and self.config.general.hide_table_titles:
            self._safe(lambda: self.backend.set_title_bar(w.handle, False), None)
        self.on_event("table_opened", {"handle": w.handle, "title": w.title, "site": site.name, "role": role})

    def _register_only(self, t: TableState) -> list:
        self.engine.tables[t.handle] = t
        return []

    def _close(self, handle, now: float) -> None:
        t = self.engine.tables.get(handle)
        self._apply(self.engine.remove_table(handle))
        self._expected.pop(handle, None)
        self._pending_move.pop(handle, None)
        self.bet_amounts.pop(handle, None)
        self._alarmed.discard(handle)
        self._last_ar_end.pop(handle, None)
        if t is not None and t.role == TABLE:
            self.session.on_table_closed(now)
            self.on_event("table_closed", {"handle": handle})

    def _detect_user_move(self, t: TableState, w: WindowInfo) -> None:
        expected = self._expected.get(t.handle)
        if expected is None or w.minimized:
            return
        moved = abs(w.rect.x - expected.x) > 8 or abs(w.rect.y - expected.y) > 8
        if not moved:
            self._pending_move.pop(t.handle, None)
            return
        # On attend que la fenêtre soit immobile sur deux balayages (fin du glisser).
        if self._pending_move.get(t.handle) == w.rect:
            self._pending_move.pop(t.handle)
            self._apply(self.engine.user_moved(t.handle, w.rect, ctrl=self._safe(self.ctrl_pressed, False)))
            if self.engine.tables[t.handle].slot_id is None:
                self._expected[t.handle] = w.rect
        else:
            self._pending_move[t.handle] = w.rect

    def _probe_action(self, t: TableState, w: WindowInfo, site: SiteDefinition, now: float) -> None:
        if not site.probe.enabled or w.minimized:
            return
        x, y = w.rect.relative_point(site.probe.fx, site.probe.fy)
        required = site.probe.matches(self._safe(lambda: self.backend.pixel(x, y), None))
        self.set_action_required(t.handle, required, now)

    def _probe_data(self, t: TableState, now: float) -> None:
        """Slots In Hand : données du fournisseur, sinon libération après inactivité."""
        data = self._snapshot(t.handle) if self.data_provider else None
        if data is not None and data.in_hand is not None:
            self._apply(self.engine.set_in_hand(t.handle, data.in_hand))
            return
        if t.in_hand and not t.needs_action:
            ended = self._last_ar_end.get(t.handle)
            if ended is not None and now - ended > IN_HAND_IDLE_S:
                self._apply(self.engine.set_in_hand(t.handle, False))

    def set_action_required(self, handle, required: bool, now: float | None = None) -> None:
        """Point d'entrée des détecteurs (sonde pixel, fournisseurs externes)."""
        now = now if now is not None else self.clock()
        with self.lock:
            t = self.engine.tables.get(handle)
            if t is None or t.needs_action == required:
                return
            cmds = self.engine.set_action_required(handle, required, now)
            self._apply(cmds, auto_focus=True)
            if required:
                last = self._last_ar_end.get(handle)
                if last is None or now - last > NEW_HAND_GAP_S:
                    self.session.on_hand()
                    goal = self.config.session.notify_hands if self.config.session.notify_hands_enabled else 0
                    if self.session.hands_goal_reached(goal):
                        self.on_event("session_hands_goal", {"hands": self.session.hands_played})
                self.session.on_action_required(auto_start=self.config.session.timer_enabled and
                                                self.config.session.start_mode == "first_dealt", now=now)
                self.on_event("action_required", {"handle": handle, "title": t.title})
            else:
                self._last_ar_end[handle] = now
                self._alarmed.discard(handle)
                self.bet_amounts.pop(handle, None)
                self.on_event("action_done", {"handle": handle})

    def set_in_hand(self, handle, in_hand: bool) -> None:
        with self.lock:
            self._apply(self.engine.set_in_hand(handle, in_hand))

    def _check_alarms(self, now: float) -> None:
        g = self.config.general
        if not g.delayed_alarm_enabled:
            return
        for t in self.engine.waiting_tables():
            if t.handle not in self._alarmed and t.action_since is not None and \
                    now - t.action_since >= g.delayed_alarm_seconds:
                self._alarmed.add(t.handle)
                self.on_event("delayed_alarm", {"handle": t.handle, "title": t.title})

    def _focus_follows_mouse(self) -> None:
        handle = self.hovered_table()
        if handle is None or handle == self._last_focus:
            return
        if self.config.general.bring_only_playing_to_front and \
                self.engine.kind_of(handle) not in (SlotKind.PLAYING, SlotKind.ACTION_REQUIRED, SlotKind.IN_HAND):
            return
        self._last_focus = handle
        self._safe(lambda: self.backend.focus(handle), None)

    def _session_tick(self, now: float) -> None:
        s_cfg = self.config.session
        if self.session.break_due(now):
            self.on_event("break_reminder", {})
        closed_for = self.session.all_closed_for(now)
        if s_cfg.stop_when_all_closed and self.session.running and closed_for is not None:
            if closed_for >= (300 if s_cfg.closed_grace_5min else 0):
                self.end_session()

    def end_session(self) -> None:
        """Arrête le minuteur, enregistre la session et repart de zéro."""
        self.session.stop()
        record = self.session.record()
        tables = self.session.current_tables
        self.session.reset()
        self.session.current_tables = tables
        self.on_event("session_ended", {"record": record})

    # ------------------------------------------------------------------ changement auto de layout
    def _auto_switch(self, before: int, after: int) -> None:
        a = self.config.auto_switch
        if not a.enabled:
            return
        target = a.layout_for(after)
        if after < before and not a.go_back_on_decrease:
            return
        if target is None or target == self.config.active_layout or self.config.layout(target) is None:
            return
        if a.ask_before:
            self._pending_switch = target
            self.on_event("ask_layout_switch", {"name": target, "tables": after})
        else:
            self.switch_layout(target)

    # ------------------------------------------------------------------ application des commandes
    def _apply(self, cmds, auto_focus: bool = False) -> None:
        for c in cmds:
            try:
                if isinstance(c, Move):
                    self.backend.move_resize(c.handle, c.rect)
                    self._expected[c.handle] = c.rect
                    self._pending_move.pop(c.handle, None)
                elif isinstance(c, Raise):
                    self.backend.bring_to_front(c.handle)
                elif isinstance(c, Focus):
                    self.backend.focus(c.handle)
                    if auto_focus and self.config.general.force_mouse_move:
                        rect = self._table_rect(c.handle)
                        if rect:
                            self.backend.set_cursor_pos(*rect.center)
            except BackendError as exc:
                log.warning("commande %s ignorée : %s", c, exc)

    # ------------------------------------------------------------------ cibles
    def table_windows(self) -> list[WindowInfo]:
        tables = {t.handle for t in self.engine.poker_tables()}
        return [w for w in self._last_windows if w.handle in tables]

    def hovered_table(self) -> Hashable | None:
        x, y = self._safe(self.backend.cursor_pos, (None, None))
        if x is None:
            return None
        w = self.backend.window_at(x, y, self.table_windows())
        return w.handle if w else None

    def target_table(self) -> Hashable | None:
        tables = {t.handle for t in self.engine.poker_tables()}
        if self.config.hotkey_settings.target == "focused":
            fg = self._safe(self.backend.foreground, None)
            if fg in tables:
                return fg
        hovered = self.hovered_table()
        if hovered is not None:
            return hovered
        urgent = self.engine.most_urgent()
        return urgent.handle if urgent else None

    # ------------------------------------------------------------------ actions
    def perform(self, action: Action, arg=None) -> None:
        with self.lock:
            self._perform(action, arg)
        self.on_event("tables", {})

    def _perform(self, action: Action, arg=None) -> None:
        reg = self.config.hotkeys
        if action == Action.DisableAllHotkeys:
            reg.globally_enabled = not reg.globally_enabled
            self.on_event("hotkeys_toggled", {"enabled": reg.globally_enabled})
            return
        if action == Action.ToggleBBMode:
            handle = self.target_table()
            if handle is not None and self._site_key(handle, action):
                return
        if action in UI_ACTIONS:
            self.on_event("ui_action", {"action": action})
            return
        if action == Action.SwitchLayout:
            self.switch_layout(arg or self.config.next_layout_name())
            return
        if action == Action.ReorderPlayingArea:
            self._apply(self.engine.reorder(SlotKind.PLAYING))
            return
        if action == Action.ReorderObserverArea:
            self._apply(self.engine.reorder(SlotKind.OBSERVER))
            return
        if action == Action.FocusMostUrgentTable:
            urgent = self.engine.most_urgent()
            if urgent:
                self._apply([Focus(urgent.handle)], auto_focus=True)
            return
        if action in (Action.BringNextTableToForeground, Action.BringPreviousTableToForeground):
            current = self._safe(self.backend.foreground, None)
            nxt = self.engine.cycle(current, 1 if action == Action.BringNextTableToForeground else -1)
            if nxt:
                self._apply([Focus(nxt.handle)])
            return
        if action == Action.CycleHoveredStack:
            x, y = self._safe(self.backend.cursor_pos, (0, 0))
            slot = self.engine.layout.slot_at(x, y)
            if slot:
                self._apply(self.engine.cycle_stack(slot.id))
            return
        if action == Action.SitOutAtAllTables:
            for t in self.engine.poker_tables():
                self._click(t.handle, "sitout_next_hand")
            return
        if action not in TABLE_ACTIONS:
            return
        tables = {t.handle for t in self.engine.poker_tables()}
        handle = arg if arg in tables else self.target_table()
        if handle is None:
            return
        self._table_action(action, handle)

    def _table_action(self, action: Action, handle) -> None:
        e = self.engine
        hs = self.config.hotkey_settings
        if action in SITE_KEY_ACTIONS and self._site_key(handle, action):
            if action in ACTING_CLICKS:
                self.set_action_required(handle, False)
            return
        if action == Action.AllIn:
            self._click(handle, "allin")
            if hs.instant_shove_allin_only or hs.instant_shove_hotkey:
                time.sleep(self.config.general.action_delay_ms / 1000)
                self._click(handle, "bet")
            self.set_action_required(handle, False)
        elif action in CLICK_ACTIONS:
            self._click(handle, CLICK_ACTIONS[action])
            if action in ACTING_CLICKS:
                self.set_action_required(handle, False)
        elif action.value.startswith("Button") and action.value[6:].isdigit():
            self._bet_button(handle, int(action.value[6:]))
        elif action in (Action.IncreaseBet, Action.DecreaseBet):
            self._adjust_bet(handle, 1 if action == Action.IncreaseBet else -1)
        elif action in (Action.SendTableToPlayingArea, Action.SendTableToPlayingSlot):
            self._apply(e.send_to_area(handle, SlotKind.PLAYING))
        elif action in (Action.SendTableToObserverArea, Action.SendTableToObserverSlot):
            self._apply(e.send_to_area(handle, SlotKind.OBSERVER))
        elif action.value.startswith("SendTableToPlayingSlot"):
            self._apply(e.send_to_slot(handle, SlotKind.PLAYING, int(action.value[-1])))
        elif action.value.startswith("SendTableToObserverSlot"):
            self._apply(e.send_to_slot(handle, SlotKind.OBSERVER, int(action.value[-1])))
        elif action == Action.MoveTableToNextSlot:
            self._apply(e.move_to_adjacent_slot(handle, 1))
        elif action == Action.MoveTableToPreviousSlot:
            self._apply(e.move_to_adjacent_slot(handle, -1))
        elif action == Action.MoveTableToNextSlotWithSwapping:
            self._apply(e.move_to_adjacent_slot(handle, 1, swap=True))
        elif action == Action.MoveTableToPreviousSlotWithSwapping:
            self._apply(e.move_to_adjacent_slot(handle, -1, swap=True))
        elif action == Action.LockTableFromDynamicFlow:
            locked = e.toggle_lock(handle)
            self.on_event("table_locked", {"handle": handle, "locked": locked})
        elif action == Action.MinimizeTable:
            self._safe(lambda: self.backend.minimize(handle), None)
        elif action == Action.CloseTable:
            self._safe(lambda: self.backend.close(handle), None)
        elif action == Action.Ignore:
            t = e.tables.get(handle)
            if t:
                self.config.ignored_titles.append(t.title)
                self._apply(e.remove_table(handle))

    def _site(self, handle) -> SiteDefinition | None:
        t = self.engine.tables.get(handle)
        return self.config.site(t.site_id) if t else None

    def _table_rect(self, handle) -> Rect | None:
        w = next((w for w in self._last_windows if w.handle == handle), None)
        return w.rect if w else (self.engine.tables[handle].rect if handle in self.engine.tables else None)

    def _site_key(self, handle, action: Action) -> bool:
        """Envoie le raccourci configuré dans le client, s'il existe (« Contournement des hotkeys »)."""
        site = self._site(handle)
        key = site.site_keys.get(SITE_KEY_ACTIONS.get(action, "")) if site else None
        if not key:
            return False
        self._safe(lambda: self.backend.focus(handle), None)
        time.sleep(self.config.general.action_delay_ms / 1000)
        self._safe(lambda: self.backend.key_combo(key), None)
        return True

    def _click(self, handle, point_name: str) -> bool:
        site, rect = self._site(handle), self._table_rect(handle)
        point = site.click_point(point_name) if site else None
        if rect is None or point is None:
            return False
        x, y = rect.relative_point(*point)
        self._safe(lambda: self.backend.click(x, y), None)
        return True

    def _type_bet(self, handle, amount: float, instant: bool = False) -> None:
        site = self._site(handle)
        if not self._click(handle, "bet_box"):
            return
        time.sleep(self.config.general.action_delay_ms / 1000)
        select_all = (site.select_all_keys if site and site.select_all_keys else
                      ("cmd+a" if self.backend.name.startswith("macOS") else "ctrl+a"))
        self._safe(lambda: self.backend.key_combo(select_all), None)
        self._safe(lambda: self.backend.type_text(format_amount(amount, self.config.general.decimal_comma)), None)
        self.bet_amounts[handle] = amount
        if instant:
            time.sleep(self.config.general.action_delay_ms / 1000)
            self._click(handle, "bet")
            self.set_action_required(handle, False)

    def _snapshot(self, handle) -> TableDataSnapshot | None:
        if self.data_provider is None:
            return None
        t = self.engine.tables.get(handle)
        try:
            return self.data_provider(handle, t.title if t else "")
        except Exception as exc:
            log.warning("fournisseur de données : %s", exc)
            return None

    def bet_context(self, handle) -> BetContext:
        t = self.engine.tables[handle]
        data = self._snapshot(handle)
        return BetContext(t.stakes.big_blind if t.stakes else None, data.street if data else "preflop",
                          data.pot if data else None, data.to_call if data else 0.0,
                          data.last_bet if data else None, data.hero_stack if data else None)

    def _bet_button(self, handle, index: int, from_overlay: bool = False) -> None:
        hs = self.config.hotkey_settings
        buttons = hs.bet_buttons
        if 1 <= index <= len(buttons):
            amount = compute_bet(buttons[index - 1], self.bet_context(handle), hs.raise_mode)
            if amount is not None:
                instant = hs.instant_shove_overlay if from_overlay else hs.instant_shove_hotkey
                self._type_bet(handle, amount, instant)
                return
        if index <= 4 and self._site_key(handle, Action(f"Button{index}")):
            return
        self._click(handle, f"button{index}")

    def overlay_bet(self, handle, index: int) -> None:
        """Clic sur l'overlay « Boutons de mise » d'une table."""
        with self.lock:
            if handle in self.engine.tables:
                self._bet_button(handle, index, from_overlay=True)

    def _adjust_bet(self, handle, direction: int) -> None:
        t = self.engine.tables[handle]
        bb = t.stakes.big_blind if t.stakes else None
        hs = self.config.hotkey_settings
        step = 0.5 if hs.wheel_step == "sb" else hs.bet_step_bb
        current = self.bet_amounts.get(handle, 2 * (bb or 1.0))
        self._type_bet(handle, adjust_bet(current, direction, bb, step))

    # ------------------------------------------------------------------ layouts
    def switch_layout(self, name: str) -> None:
        layout = self.config.layout(name)
        if layout is None:
            return
        with self.lock:
            self.config.active_layout = layout.name
            self._apply(self.engine.set_layout(layout))
        self.on_event("layout_changed", {"name": layout.name})

    def confirm_pending_switch(self, accept: bool) -> None:
        name, self._pending_switch = self._pending_switch, None
        if accept and name:
            self.switch_layout(name)

    def reload_settings(self) -> None:
        with self.lock:
            self.engine.settings = self.config.placement
            self.session.break_every_min = self.config.general.break_every_min
            layout = self.config.layout()
            if layout is not self.engine.layout:
                self._apply(self.engine.set_layout(layout))

    def refresh_screens(self) -> list[Rect]:
        self.screens = self._safe(self.backend.screens, self.screens)
        return self.screens

    # ------------------------------------------------------------------ instantané pour l'UI
    def snapshot(self) -> list[dict]:
        with self.lock:
            rows = []
            for t in self.engine.ordered_tables():
                slot = self.engine.layout.slot(t.slot_id) if t.slot_id is not None else None
                site = self.config.site(t.site_id)
                rows.append({
                    "handle": t.handle, "site": site.name if site else t.site_id, "title": t.title,
                    "slot": slot, "slot_number": self.engine.layout.number_of(slot) if slot else None,
                    "action": t.needs_action, "locked": t.locked, "in_hand": t.in_hand,
                    "stakes": f"{t.stakes.small_blind:g}/{t.stakes.big_blind:g}" if t.stakes else "",
                })
            return rows

    def counters(self) -> dict:
        with self.lock:
            return {"tables": self.table_count(), "ar": len(self.engine.waiting_tables()),
                    "stacked": self.engine.stacked_count(), "hands": self.session.hands_played}
