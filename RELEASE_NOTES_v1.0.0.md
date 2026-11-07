# AutoClicker v1.0.0

AutoClicker v1.0.0 is the first release with GitHub Releases update support. It provides a compact Turkish Windows interface for configuring independent left- and right-click automation.

## Features

- **Independent left and right clickers:** Configure each side separately and run them at the same time.
- **1–60 clicks per second:** Adjust each clicker with its own CPS slider.
- **Keyboard or mouse triggers:** Assign a different key or mouse button to each clicker. Defaults are `F6` for left click and `F7` for right click.
- **Hold and toggle modes:** Hold a trigger to click while pressed, or toggle clicking on and off with repeated presses.
- **Optional speed variation:** Vary the actual speed up to 3 CPS below the selected value, with a minimum of 1 CPS.
- **Live feedback:** View the active/idle status and measured CPS for both clickers.
- **Custom background:** Choose a PNG, JPG/JPEG, BMP, GIF, or WebP image. The selected background is stored in the user profile.
- **Automatic update checks:** Check the latest stable GitHub Release when the app starts and prompt before downloading or restarting.
- **Verified, recoverable updates:** Verify the release ZIP using SHA-256, stage the new files, keep backups, and restore the previous files if the new app fails its startup confirmation.

## Install

Download `AutoClicker-Windows.zip` and extract all three files into the same writable folder:

- `AutoClicker.exe`
- `AutoClickerUpdater.exe`
- `updater_config.json`

Run `AutoClicker.exe`. Existing settings and custom backgrounds remain under `%APPDATA%\AutoClicker2`; the updater does not replace those files. Users moving from an older EXE need to install this update-enabled release once manually.

## Notes

- The public repository is configured as `bekiryarbasar/AutoClicker`.
- Release assets must include `AutoClicker-Windows.zip` and `SHA256SUMS.txt`.
- This release is built for Windows with Python 3.12 and PyInstaller 6.22.3.
