import json
import os
import tempfile
import unittest
from pathlib import Path

from fukuroku import betsizing, gamepad, pokermath, rng
from fukuroku.backends.dummy import DummyBackend
from fukuroku.backends.linux_x11 import parse_wmctrl, parse_xrandr
from fukuroku.backends.macos import parse_window_list
from fukuroku.config import Config
from fukuroku.geometry import Rect
from fukuroku.hotkeys import Action, HotKey, HotKeyCollisionError, HotKeyRegistry, default_registry
from fukuroku.inputs import ChordTracker
from fukuroku.layout import Layout, Slot, SlotKind, auto_layout, best_grid, build_preset, grid_layout
from fukuroku.manager import TableManager
from fukuroku.placement import Move, PlacementEngine, Raise, TableState
from fukuroku.sites import Stakes, StakeTier, default_sites, parse_stakes

SCREEN = Rect(0, 0, 1920, 1080)


class GeometryTests(unittest.TestCase):
    def test_fit_aspect_wide(self):
        r = Rect(0, 0, 1000, 500).fit_aspect(1.0)
        self.assertEqual(r, Rect(250, 0, 500, 500))

    def test_fit_aspect_tall(self):
        r = Rect(0, 0, 400, 1000).fit_aspect(2.0)
        self.assertEqual(r, Rect(0, 400, 400, 200))

    def test_relative_point(self):
        self.assertEqual(Rect(100, 100, 200, 100).relative_point(0.5, 0.5), (200, 150))


class LayoutTests(unittest.TestCase):
    def test_grid_layout(self):
        lay = grid_layout("g", [SCREEN], 2, 2)
        self.assertEqual(len(lay.slots), 4)
        self.assertEqual(lay.slots[3].rect, Rect(960, 540, 960, 540))

    def test_best_grid(self):
        self.assertEqual(best_grid(SCREEN, 4), (2, 2))
        cols, rows = best_grid(SCREEN, 6)
        self.assertGreaterEqual(cols * rows, 6)

    def test_auto_layout_observer(self):
        lay = auto_layout("a", [SCREEN], 4, observer_ratio=0.25)
        self.assertEqual(len(lay.playing_slots), 4)
        self.assertTrue(lay.observer_slots)
        self.assertTrue(all(s.capacity == 0 for s in lay.observer_slots))

    def test_multi_screen(self):
        lay = auto_layout("a", [SCREEN, Rect(1920, 0, 1920, 1080)], 8)
        self.assertEqual(len(lay.slots), 8)
        self.assertEqual(sum(1 for s in lay.slots if s.rect.x >= 1920), 4)

    def test_roundtrip(self):
        lay = build_preset("auto_observer", "x", [SCREEN], 6)
        self.assertEqual(Layout.from_dict(json.loads(json.dumps(lay.to_dict()))).to_dict(), lay.to_dict())


def two_zone_layout():
    return Layout("t", [
        Slot(1, SlotKind.PLAYING, Rect(0, 0, 960, 660)),
        Slot(2, SlotKind.PLAYING, Rect(960, 0, 960, 660)),
        Slot(3, SlotKind.OBSERVER, Rect(0, 700, 1920, 380), capacity=0),
    ], None)


def ar_layout():
    return Layout("ar", [
        Slot(1, SlotKind.PLAYING, Rect(0, 0, 640, 440)),
        Slot(2, SlotKind.PLAYING, Rect(640, 0, 640, 440)),
        Slot(3, SlotKind.ACTION_REQUIRED, Rect(0, 500, 960, 580)),
        Slot(4, SlotKind.QUEUE, Rect(1280, 0, 640, 440), capacity=0),
    ], None)


def table(h, t=0.0):
    return TableState(h, "pokerstars", f"T{h}", Rect(0, 0, 800, 550), arrival=t)


class PlacementTests(unittest.TestCase):
    def test_new_tables_fill_playing_then_observer(self):
        e = PlacementEngine(two_zone_layout())
        for h in (1, 2, 3):
            e.add_table(table(h, h))
        self.assertEqual([e.tables[h].slot_id for h in (1, 2, 3)], [1, 2, 3])

    def test_action_required_moves_to_ar_slot_and_back(self):
        e = PlacementEngine(ar_layout())
        e.add_table(table(1))
        cmds = e.set_action_required(1, True, 10)
        self.assertEqual(e.kind_of(1), SlotKind.ACTION_REQUIRED)
        self.assertTrue(any(isinstance(c, Move) for c in cmds))
        e.set_action_required(1, False, 11)
        self.assertEqual(e.tables[1].slot_id, 1)

    def test_locked_table_stays(self):
        e = PlacementEngine(two_zone_layout())
        e.add_table(table(1))
        e.set_action_required(1, True, 1)
        e.toggle_lock(1)
        e.set_action_required(1, False, 2)
        self.assertIn(e.tables[1].slot_id, (1, 2))

    def test_queue_promoted_when_ar_slot_frees(self):
        e = PlacementEngine(ar_layout())
        for h in (1, 2):
            e.add_table(table(h, h))
        e.set_action_required(1, True, 10)
        e.set_action_required(2, True, 11)
        self.assertEqual(e.kind_of(2), SlotKind.QUEUE)
        e.set_action_required(1, False, 20)
        self.assertEqual(e.kind_of(2), SlotKind.ACTION_REQUIRED)
        self.assertEqual(e.tables[1].slot_id, 1)

    def test_stack_urgency_raises_oldest(self):
        lay = Layout("s", [Slot(1, SlotKind.PLAYING, Rect(0, 0, 800, 600), capacity=0)], None)
        e = PlacementEngine(lay)
        e.add_table(table(1, 1))
        e.add_table(table(2, 2))
        e.set_action_required(2, True, 5)
        cmds = e.set_action_required(1, True, 6)
        self.assertIn(Raise(2), cmds)  # 2 attend depuis plus longtemps
        self.assertEqual(e.most_urgent().handle, 2)

    def test_magnetize(self):
        e = PlacementEngine(two_zone_layout())
        e.settings.dynamic_flow = False
        e.add_table(table(1))
        e.user_moved(1, Rect(900, 10, 800, 550))
        self.assertEqual(e.tables[1].slot_id, 2)

    def test_move_with_swap(self):
        lay = grid_layout("g", [SCREEN], 2, 1, aspect=None)
        e = PlacementEngine(lay)
        e.add_table(table(1, 1))
        e.add_table(table(2, 2))
        self.assertEqual((e.tables[1].slot_id, e.tables[2].slot_id), (1, 2))
        e.move_to_adjacent_slot(1, 1, swap=True)
        self.assertEqual((e.tables[1].slot_id, e.tables[2].slot_id), (2, 1))

    def test_cycle(self):
        e = PlacementEngine(grid_layout("g", [SCREEN], 3, 1))
        for h in (1, 2, 3):
            e.add_table(table(h, h))
        self.assertEqual(e.cycle(1, 1).handle, 2)
        self.assertEqual(e.cycle(1, -1).handle, 3)

    def test_overflow_stacks(self):
        e = PlacementEngine(grid_layout("g", [SCREEN], 1, 1))
        e.add_table(table(1, 1))
        e.add_table(table(2, 2))
        self.assertEqual(e.tables[2].slot_id, 1)

    def test_remove_promotes(self):
        e = PlacementEngine(ar_layout())
        for h in (1, 2):
            e.add_table(table(h, h))
            e.set_action_required(h, True, h)
        e.remove_table(1)
        self.assertEqual(e.kind_of(2), SlotKind.ACTION_REQUIRED)


class SitesTests(unittest.TestCase):
    def test_stakes(self):
        self.assertEqual(parse_stakes("Halley II - $0.25/$0.50 USD - No Limit Hold'em"), Stakes(0.25, 0.5, "$"))
        self.assertEqual(parse_stakes("Table 5 €1/€2"), Stakes(1, 2, "€"))
        self.assertEqual(parse_stakes("NL50 Zoom"), Stakes(0.25, 0.5))
        self.assertEqual(parse_stakes("Blinds 1k/2k"), Stakes(1000, 2000, ""))
        self.assertIsNone(parse_stakes("Lobby"))
        self.assertEqual(StakeTier.classify(Stakes(0.5, 1)), StakeTier.MID)

    def test_pokerstars_detection(self):
        ps = next(s for s in default_sites() if s.id == "pokerstars")
        self.assertTrue(ps.matches_process("C:\\Program Files\\PokerStars\\PokerStars.exe"))
        self.assertTrue(ps.is_table("Halley - $0.05/$0.10 USD - NLHE", "", 800, 550))
        self.assertFalse(ps.is_table("PokerStars Lobby", "", 1000, 700))


class HotkeyTests(unittest.TestCase):
    def test_parse(self):
        hk = HotKey.parse("Shift+Ctrl+F")
        self.assertEqual(str(hk), "ctrl+shift+f")
        self.assertEqual(HotKey.parse("wheelup").key, "wheel_up")
        with self.assertRaises(ValueError):
            HotKey.parse("a+b")

    def test_collision_and_restricted(self):
        reg = HotKeyRegistry()
        reg.bind(Action.Fold, "f1")
        with self.assertRaises(HotKeyCollisionError):
            reg.bind(Action.Check, "f1")
        with self.assertRaises(HotKeyCollisionError):
            reg.bind(Action.Check, "alt+f4")

    def test_disable_all(self):
        reg = default_registry()
        reg.globally_enabled = False
        self.assertIsNone(reg.resolve(HotKey.parse("f1")))
        self.assertEqual(reg.resolve(HotKey.parse("ctrl+alt+h")), Action.DisableAllHotkeys)

    def test_roundtrip(self):
        reg = default_registry()
        self.assertEqual(HotKeyRegistry.from_dict(reg.to_dict()).to_dict(), reg.to_dict())

    def test_all_original_actions_present(self):
        # AppHotKeyName d'origine : 67 champs dont « value__ » → 66 actions.
        self.assertEqual(len(Action), 66)

    def test_chord_tracker(self):
        got = []
        tr = ChordTracker(got.append)
        tr.press("ctrl")
        tr.press("f")
        tr.press("f")  # répétition ignorée
        tr.release("f")
        tr.release("ctrl")
        tr.tap("wheel_up")
        self.assertEqual([str(h) for h in got], ["ctrl+f", "wheel_up"])


class MathTests(unittest.TestCase):
    def test_pot_odds(self):
        self.assertAlmostEqual(pokermath.pot_odds(150, 50), 0.25)

    def test_mdf_and_bluff(self):
        self.assertAlmostEqual(pokermath.mdf(100, 50), 2 / 3)
        self.assertAlmostEqual(pokermath.bluff_break_even(100, 100), 0.5)
        self.assertAlmostEqual(pokermath.bluff_ratio(100, 100), 1 / 3)

    def test_outs(self):
        self.assertAlmostEqual(pokermath.outs_equity(9, 2), 0.3497, places=3)
        self.assertAlmostEqual(pokermath.outs_equity(9, 1), 9 / 46, places=6)

    def test_spr(self):
        self.assertEqual(pokermath.spr(500, 100), 5)
        self.assertEqual(pokermath.effective_stack(300, [100, 500]), 300)


class BetTests(unittest.TestCase):
    def ctx(self, bb=1.0, street="preflop", pot=None, to_call=0.0, last_bet=None, stack=None):
        return betsizing.BetContext(bb, street, pot, to_call, last_bet, stack)

    def test_bb(self):
        self.assertEqual(betsizing.compute_bet(betsizing.BetButton(2.5), self.ctx(0.5)), 1.25)

    def test_pot_needs_data(self):
        button = betsizing.BetButton(None, 50)
        self.assertIsNone(betsizing.compute_bet(button, self.ctx(street="flop", to_call=2, last_bet=2)))
        self.assertEqual(betsizing.compute_bet(button, self.ctx(street="flop", pot=10, to_call=2, last_bet=2)), 9.0)

    def test_times_when_facing_raise(self):
        button = betsizing.BetButton(2.5, None, 3)
        self.assertEqual(betsizing.compute_bet(button, self.ctx(last_bet=3), betsizing.RaiseMode("times")), 9.0)

    def test_cap_and_format(self):
        self.assertEqual(betsizing.compute_bet(betsizing.BetButton(100), self.ctx(stack=40)), 40)
        self.assertEqual(betsizing.format_amount(1.5, True), "1,5")
        self.assertEqual(betsizing.format_amount(2.0), "2")

    def test_legacy_bet_size_migration(self):
        self.assertEqual(betsizing.BetButton.from_dict({"name": "x", "mode": "pot", "value": 0.5}).postflop_pct, 50)


class GamepadTests(unittest.TestCase):
    def test_combo(self):
        self.assertEqual(gamepad.resolve_combo("DPadLeft", {"LeftButton"}), "DPadLeftPlusLeftButton")
        self.assertEqual(gamepad.resolve_combo("DPadUp", {"LeftButton", "RightButton"}), "DPadUpPlusLeftPlusRightButton")

    def test_edges(self):
        ed = gamepad.EdgeDetector()
        self.assertEqual(ed.update({"A"}), ["A"])
        self.assertEqual(ed.update({"A"}), [])
        self.assertEqual(ed.update({"LeftButton"}), ["LeftButton"])
        self.assertEqual(ed.update({"LeftButton", "DPadLeft"}), ["DPadLeftPlusLeftButton"])

    def test_names_match_original(self):
        self.assertEqual(len(gamepad.GAMEPAD_BUTTONS), 38)


class RngTests(unittest.TestCase):
    def test_range(self):
        vals = {rng.draw(0, 3) for _ in range(500)}
        self.assertEqual(vals, {0, 1, 2, 3})

    def test_color(self):
        s = rng.RngSettings()
        self.assertEqual(rng.color_for(10, s), "#d9534f")
        self.assertEqual(rng.color_for(95, s), "#5cb85c")


class ParserTests(unittest.TestCase):
    def test_wmctrl(self):
        out = "0x04200007  0 4242   10   20   800  550  pokerstars.exe.PokerStars.exe  host Halley - $0.05/$0.10\n"
        rows = parse_wmctrl(out)
        self.assertEqual(rows[0]["title"], "Halley - $0.05/$0.10")
        self.assertEqual(rows[0]["cls"], "pokerstars.exe.PokerStars.exe")

    def test_xrandr(self):
        out = "HDMI-1 connected primary 1920x1080+0+0 (normal)\nDP-1 connected 2560x1440+1920+0\n"
        self.assertEqual(parse_xrandr(out), [Rect(0, 0, 1920, 1080), Rect(1920, 0, 2560, 1440)])

    def test_macos(self):
        out = "123\tPokerStars\t1\t10\t20\t800\t550\tfalse\tHalley - $0.05/$0.10\n"
        w = parse_window_list(out)[0]
        self.assertEqual((w.handle, w.process_name, w.rect), ("123:1", "PokerStars", Rect(10, 20, 800, 550)))


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["FUKUROKU_HOME"] = self.tmp.name
        self.backend = DummyBackend()
        self.cfg = Config()
        self.cfg.layouts = [grid_layout("g", [SCREEN], 2, 2)]
        self.clock = [0.0]
        self.mgr = TableManager(self.cfg, self.backend, clock=lambda: self.clock[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_places_tables_and_ignores_lobby(self):
        t1 = self.backend.add_window("Halley - $0.05/$0.10 USD", "PokerStars.exe", Rect(5, 5, 800, 550))
        self.backend.add_window("PokerStars Lobby", "PokerStars.exe", Rect(5, 5, 1000, 700))
        self.backend.add_window("Notes", "gedit", Rect(5, 5, 800, 550))
        self.mgr.scan()
        self.assertEqual(list(self.mgr.engine.tables), [t1])
        self.assertEqual(self.backend.windows[t1].rect, self.cfg.layouts[0].slots[0].rect.fit_aspect(800 / 550))
        self.backend.remove_window(t1)
        self.mgr.scan()
        self.assertEqual(self.mgr.engine.tables, {})

    def test_fold_clicks_hovered_table(self):
        h = self.backend.add_window("Halley - $0.05/$0.10", "PokerStars.exe", Rect(5, 5, 800, 550))
        self.mgr.scan()
        r = self.backend.windows[h].rect
        self.backend.cursor = r.relative_point(0.5, 0.5)
        self.mgr.perform(Action.Fold)
        clicks = [e for e in self.backend.log if e[0] == "click"]
        self.assertEqual(clicks[-1][1:3], r.relative_point(0.62, 0.92))

    def test_bet_button_types_amount(self):
        h = self.backend.add_window("Halley - $0.25/$0.50", "PokerStars.exe", Rect(5, 5, 800, 550))
        self.mgr.scan()
        self.backend.cursor = self.backend.windows[h].rect.relative_point(0.5, 0.5)
        self.mgr.perform(Action.Button2)  # 2.5 BB
        self.assertIn(("type", "1.25"), self.backend.log)

    def test_pixel_probe_action_required(self):
        h = self.backend.add_window("Halley - $0.05/$0.10", "PokerStars.exe", Rect(5, 5, 800, 550))
        site = self.cfg.site("pokerstars")
        site.probe.enabled = True
        self.mgr.scan()
        r = self.backend.windows[h].rect
        self.backend.pixels[r.relative_point(site.probe.fx, site.probe.fy)] = site.probe.color
        self.mgr.scan()
        self.assertTrue(self.mgr.engine.tables[h].needs_action)

    def test_user_move_magnetizes(self):
        h = self.backend.add_window("Halley - $0.05/$0.10", "PokerStars.exe", Rect(5, 5, 800, 550))
        self.mgr.scan()
        self.backend.windows[h].rect = Rect(1000, 560, 800, 550)
        self.mgr.scan()
        self.mgr.scan()
        self.assertEqual(self.mgr.engine.tables[h].slot_id, 4)

    def test_switch_layout(self):
        self.cfg.layouts.append(grid_layout("h", [SCREEN], 1, 1))
        self.backend.add_window("Halley - $0.05/$0.10", "PokerStars.exe", Rect(5, 5, 800, 550))
        self.mgr.scan()
        self.mgr.perform(Action.SwitchLayout)
        self.assertEqual(self.cfg.active_layout, "h")

    def test_config_roundtrip(self):
        path = Path(self.tmp.name) / "c.json"
        self.cfg.save(path)
        again = Config.load(path)
        self.assertEqual(again.to_dict(), self.cfg.to_dict())


if __name__ == "__main__":
    unittest.main()
