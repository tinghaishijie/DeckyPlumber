import os
import shlex
import subprocess
import time

import decky_plugin
import device
import mapping_profiles
import plugin_enums
import plugin_settings as settings

STATE_FILE = "/tmp/.inputplumber.state"
DEST = "org.shadowblip.InputPlumber"
DEVICE_PATH = "/org/shadowblip/InputPlumber/CompositeDevice0"
DEVICE_INTERFACE = "org.shadowblip.Input.CompositeDevice"
TARGET_INTERFACE = "org.shadowblip.Input.Target"


def clear_state_file():
    """Discard legacy cache on plugin startup; it is never proof of live state."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def get_env():
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ""
    return env


def _run(args):
    return subprocess.run(
        args, check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=get_env(), timeout=2,
    )


def _property(path, interface, name):
    return shlex.split(_run([
        "busctl", "get-property", DEST, path, interface, name,
    ]).stdout)


def get_target_device_ids():
    """Read actual target types, including after InputPlumber recreates devices."""
    paths = _property(DEVICE_PATH, DEVICE_INTERFACE, "TargetDevices")
    if len(paths) < 2 or paths[0] != "ao" or int(paths[1]) != len(paths[2:]):
        raise RuntimeError("Invalid InputPlumber TargetDevices response")
    targets = []
    for path in paths[2:]:
        value = _property(path, TARGET_INTERFACE, "DeviceType")
        if len(value) != 2 or value[0] != "s":
            raise RuntimeError("Invalid InputPlumber DeviceType response")
        targets.append(value[1])
    return targets


def _desired_targets(mode):
    targets = [mode, "keyboard", "mouse"]
    if device.is_ayaneo_flip():
        targets.append("touchscreen")
    return targets


def sync_controller_settings(current_game_id, refresh_mappings=True):
    controller_profile = settings.get_controller_profile_for_game_id(current_game_id)
    mode = controller_profile.get("mode", "default")
    changed = set_controller_mode(mode)
    # Avoid reloading mappings on every recovery check when nothing changed.
    if changed or refresh_mappings:
        active_profiles = controller_profile.get("activeProfiles", [])
        merge_base = settings.get_settings().get("mergeBaseProfile", True)
        mapping_profiles.apply_mapping_profiles(active_profiles, merge_base=merge_base)


def set_controller_mode(mode):
    """Reconcile live targets; a stale state file must never skip recovery."""
    if mode == plugin_enums.ControllerModes.DEFAULT.value:
        if not os.path.exists(STATE_FILE):
            return False
        # Returning to Default relinquishes control to the distribution.
        _run(["systemctl", "restart", "inputplumber"])
        os.remove(STATE_FILE)
        _wait_for_inputplumber_dbus()
        mapping_profiles.capture_base_profile()
        return True

    desired = _desired_targets(mode)
    actual = get_target_device_ids()
    if sorted(actual) == sorted(desired):
        # Remember ownership for a later explicit switch back to Default.
        with open(STATE_FILE, "w") as state:
            state.write(mode)
        return False

    decky_plugin.logger.info(f"Restoring controller targets: {actual} -> {desired}")
    _run([
        "busctl", "call", DEST, DEVICE_PATH, DEVICE_INTERFACE,
        "SetTargetDevices", "as", str(len(desired)), *desired,
    ])
    with open(STATE_FILE, "w") as state:
        state.write(mode)
    return True


def _wait_for_inputplumber_dbus(timeout=5, interval=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _property(DEVICE_PATH, DEVICE_INTERFACE, "ProfileName")
            return
        except (subprocess.SubprocessError, OSError):
            time.sleep(interval)
    raise RuntimeError("InputPlumber did not become ready after restart")
