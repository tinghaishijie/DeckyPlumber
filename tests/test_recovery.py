import asyncio
import importlib
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))
from controller_recovery import ControllerRecovery


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sync = Mock()
        self.recovery = ControllerRecovery(self.sync, Mock())
        self.recovery.DELAYS = (0, 0, 0)

    async def asyncTearDown(self):
        await self.recovery.close()

    async def test_unavailable_device_is_retried(self):
        self.sync.side_effect = [RuntimeError("not ready"), None, None]
        self.recovery.request("42")
        await self.recovery.task
        self.assertEqual(self.sync.call_count, 3)
        self.assertEqual([c.kwargs["refresh_mappings"] for c in self.sync.call_args_list],
                         [True, True, False])

    async def test_late_reset_is_checked_after_initial_success(self):
        self.recovery.request("42")
        await self.recovery.task
        self.assertEqual(self.sync.call_count, 3)
        self.sync.assert_called_with("42", refresh_mappings=False)

    async def test_new_profile_cancels_stale_recovery(self):
        self.recovery.request("old")
        self.recovery.request("new")
        await self.recovery.task
        self.assertTrue(all(c.args == ("new",) for c in self.sync.call_args_list))

    async def test_suspend_stops_work_and_resume_uses_current_game(self):
        self.recovery.request("old")
        self.recovery.suspend()
        self.recovery.request("while-suspended")
        await asyncio.sleep(0)
        self.sync.assert_not_called()
        self.recovery.resume("resumed-game")
        await self.recovery.task
        self.sync.assert_called_with("resumed-game", refresh_mappings=False)

    async def test_unload_cancels_and_prevents_late_callbacks(self):
        self.recovery.request("42")
        await self.recovery.close()
        self.recovery.resume("late")
        await asyncio.sleep(0)
        self.sync.assert_not_called()


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.mapping = Mock()
        self.settings = Mock()
        self.settings.get_controller_profile_for_game_id.return_value = {
            "mode": "xbox-elite", "activeProfiles": ["custom"]}
        self.settings.get_settings.return_value = {"mergeBaseProfile": True}
        self.device = Mock()
        self.device.is_ayaneo_flip.return_value = False
        self.modules = patch.dict(sys.modules, {
            "decky_plugin": types.SimpleNamespace(logger=logging.getLogger("tests")),
            "device": self.device, "mapping_profiles": self.mapping,
            "plugin_settings": self.settings,
        })
        self.modules.start()
        sys.modules.pop("controller_utils", None)
        self.utils = importlib.import_module("controller_utils")
        self.utils.STATE_FILE = os.path.join(self.temp.name, "state")
        self.live = ["deck-uhid", "keyboard", "mouse"]
        self.commands = []
        self.run = patch.object(self.utils, "_run", side_effect=self.busctl)
        self.run.start()

    def tearDown(self):
        self.run.stop()
        self.modules.stop()
        sys.modules.pop("controller_utils", None)
        self.temp.cleanup()

    def busctl(self, args):
        self.commands.append(args)
        if args[:2] == ["busctl", "get-property"]:
            if args[-1] == "TargetDevices":
                paths = [f'"/org/shadowblip/InputPlumber/devices/target/{i}"'
                         for i in range(len(self.live))]
                return types.SimpleNamespace(stdout=f'ao {len(paths)} ' + ' '.join(paths))
            if args[-1] == "DeviceType":
                index = int(args[3].rsplit("/", 1)[1])
                return types.SimpleNamespace(stdout=f's "{self.live[index]}"')
            if args[-1] == "ProfileName":
                return types.SimpleNamespace(stdout='s "Default"')
        if "SetTargetDevices" in args:
            self.live = args[8:]
            return types.SimpleNamespace(stdout="")
        if args == ["systemctl", "restart", "inputplumber"]:
            self.live = ["deck-uhid", "keyboard", "mouse"]
            return types.SimpleNamespace(stdout="")
        raise AssertionError(args)

    def writes(self):
        return [c for c in self.commands if "SetTargetDevices" in c]

    def test_stale_cache_does_not_skip_real_mode_restore(self):
        Path(self.utils.STATE_FILE).write_text("xbox-elite")
        self.utils.sync_controller_settings("42")
        self.assertEqual(self.live, ["xbox-elite", "keyboard", "mouse"])
        self.assertEqual(len(self.writes()), 1)
        self.mapping.apply_mapping_profiles.assert_called_once_with(["custom"], merge_base=True)

    def test_matching_live_targets_are_not_recreated(self):
        self.live = ["keyboard", "mouse", "xbox-elite"]
        self.utils.sync_controller_settings("42", refresh_mappings=False)
        self.assertEqual(self.writes(), [])
        self.mapping.apply_mapping_profiles.assert_not_called()

    def test_late_external_reset_is_repaired_and_remapped(self):
        self.utils.sync_controller_settings("42")
        self.live = ["deck-uhid", "keyboard", "mouse"]
        self.utils.sync_controller_settings("42", refresh_mappings=False)
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.mapping.apply_mapping_profiles.call_count, 2)

    def test_unavailable_device_propagates_for_retry(self):
        with patch.object(self.utils, "get_target_device_ids", side_effect=RuntimeError("missing")):
            with self.assertRaises(RuntimeError):
                self.utils.sync_controller_settings("42")
        self.assertFalse(Path(self.utils.STATE_FILE).exists())
        self.mapping.apply_mapping_profiles.assert_not_called()

    def test_failed_write_does_not_claim_success(self):
        original = self.busctl
        def fail_write(args):
            if "SetTargetDevices" in args:
                raise subprocess.CalledProcessError(1, args)
            return original(args)
        with patch.object(self.utils, "_run", side_effect=fail_write):
            with self.assertRaises(subprocess.CalledProcessError):
                self.utils.set_controller_mode("xbox-elite")
        self.assertFalse(Path(self.utils.STATE_FILE).exists())

    def test_default_relinquishes_control_only_once(self):
        Path(self.utils.STATE_FILE).write_text("xbox-elite")
        self.assertTrue(self.utils.set_controller_mode("default"))
        self.assertFalse(self.utils.set_controller_mode("default"))
        self.assertEqual(self.commands.count(["systemctl", "restart", "inputplumber"]), 1)
        self.assertEqual(self.writes(), [])

    def test_flip_keeps_touchscreen_target(self):
        self.device.is_ayaneo_flip.return_value = True
        self.utils.set_controller_mode("xbox-elite")
        self.assertEqual(self.live, ["xbox-elite", "keyboard", "mouse", "touchscreen"])

    def test_recovery_rereads_latest_saved_profile(self):
        self.utils.sync_controller_settings("42")
        self.settings.get_controller_profile_for_game_id.return_value = {"mode": "ds5"}
        self.utils.sync_controller_settings("42", refresh_mappings=False)
        self.assertEqual(self.live, ["ds5", "keyboard", "mouse"])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        manager = Mock()
        self.modules = patch.dict(sys.modules, {"settings": types.SimpleNamespace(SettingsManager=manager)})
        self.modules.start()
        self.env = patch.dict(os.environ, {"DECKY_PLUGIN_SETTINGS_DIR": "/tmp"})
        self.env.start()
        sys.modules.pop("plugin_settings", None)
        self.settings = importlib.import_module("plugin_settings")
        self.settings.setting_file.settings = {
            "controllerProfiles": {"default": {"mode": "xbox-elite"}},
            "perGameProfilesEnabled": True,
        }

    def tearDown(self):
        self.env.stop()
        self.modules.stop()
        sys.modules.pop("plugin_settings", None)

    def test_new_game_falls_back_to_saved_global_profile(self):
        self.assertEqual(self.settings.get_controller_profile_for_game_id("new"), {"mode": "xbox-elite"})

    def test_new_game_respects_always_default_option(self):
        self.settings.setting_file.settings["advanced"] = {"ALWAYS_USE_DEFAULT": True}
        self.assertEqual(self.settings.get_controller_profile_for_game_id("new"), {"mode": "default"})

    def test_fresh_install_has_valid_profile(self):
        self.settings.setting_file.settings = {}
        self.assertEqual(self.settings.get_controller_profile_for_game_id("default"), {"mode": "default"})


if __name__ == "__main__":
    unittest.main()
