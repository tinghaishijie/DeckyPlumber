# DeckyPlumber - Decky Plugin

[![](https://img.shields.io/github/downloads/tinghaishijie/DeckyPlumber/total.svg)](https://github.com/tinghaishijie/DeckyPlumber/releases)

Decky Plugin for changing InputPlumber controller mode

![image 1, thanks to honjow](./img/1.jpg)
![image 2 thanks to honjow](./img/2.jpg)
![image 3, thanks to honjow](./img/3.jpg)

## Startup and resume recovery (this fork)

This fork preserves the selected controller mode across plugin startup and
reconciles InputPlumber targets after resume. It fixes a startup ordering race
that could overwrite saved modes with Default, reads live target types instead
of trusting a temporary cache, and checks again for up to 30 seconds after each
startup/profile-change/resume request. An early success does not stop these
checks, so a later SteamOS target reset can also be corrected. Matching targets
are left alone; recovery is cancelled on suspend/unload and superseded by newer
settings. No system suspend service is disabled and no system configuration is
modified.

The recovery uses the same CompositeDevice0 as upstream DeckyPlumber. It does
not add multi-controller selection or guarantee recovery if a device remains
unavailable beyond the retry window. Select the desired mode again to start a
new recovery window. InputPlumber and working hardware rumble support are still
required; this is not a kernel or firmware patch.

Automated tests cover settings-load ordering, stale caches, delayed device
availability, later target resets, profile changes, and cancellation. Hardware
rumble and repeated sleep/reboot cycles on MSI Claw A8 have not been tested by
the fork maintainer. On an A8 where Xbox Elite already enables rumble, choose
Xbox Elite in the plugin, then validate a cold boot and repeated sleep/resume
cycles, including waking with a game running. Existing per-game profiles are
preserved and may override the global selection.

To inspect the actual state (the UI shows the saved selection):

```bash
inputplumber --version
inputplumber devices list
inputplumber device 0 targets list
```

Plugin logs are under `~/homebrew/logs/DeckyPlumber/`. Check these after a failed
resume. Return to Default to relinquish controller-mode control to SteamOS.

Upstream project: [aarron-lee/DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber).
The startup race is also described in [upstream PR #19](https://github.com/aarron-lee/DeckyPlumber/pull/19).

# Prerequisites

Works only on devices with InputPlumber running. Also requires python yaml installed.

# Install

### Prerequisites

Decky Loader must already be installed. Python yaml is also required, most gaming distros should already have it pre-installed. 

**NOTE for CachyOS users**: you will need to install python yaml, it is NOT preinstalled by default.

### Quick Install / Update

Run the following in terminal, then reboot. Note that this works both for installing or updating the plugin

```
curl -fLsS https://raw.githubusercontent.com/tinghaishijie/DeckyPlumber/v0.1.9/install.sh | VERSION=v0.1.9 bash

```

### Manual Install

Download the latest release from the [releases page](https://github.com/tinghaishijie/DeckyPlumber/releases)

Unzip the `tar.gz` file, and move the `DeckyPlumber` folder to your `$HOME/homebrew/plugins` directory

then run:

```
sudo systemctl restart plugin_loader.service
```

then reboot your machine. Saved settings are kept in `~/homebrew/settings/DeckyPlumber`.

The installer verifies the release SHA-256 checksum and stages the archive
before replacing the plugin. It preserves settings and attempts rollback if
installation fails. Install/update briefly restarts Decky and its other plugins.
Plugin updates in this fork use this fork's releases, not upstream releases.

## Manual build

Dependencies:

- Node.js 22 and pnpm 8.15.4
- Python 3 and PyYAML

```bash
git clone https://github.com/tinghaishijie/DeckyPlumber.git

cd DeckyPlumber

# if pnpm not already installed
npm install -g pnpm@8.15.4

pnpm install --frozen-lockfile
pnpm run typecheck
pnpm test
python3 -m unittest discover -s tests -v
pnpm run build
python3 scripts/package.py
```

Extract `out/DeckyPlumber.tar.gz` into `~/homebrew/plugins`, then restart your plugin service

```bash
sudo systemctl restart plugin_loader.service
```

# Attribution

Built using Decky Plugin Template: https://github.com/SteamDeckHomebrew/decky-plugin-template/
