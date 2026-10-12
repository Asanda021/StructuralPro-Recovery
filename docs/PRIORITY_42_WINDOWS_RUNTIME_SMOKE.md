# Priority 42 — Windows Runtime Smoke

## Goal
Verify that the actual desktop application can initialize and exit cleanly on a Windows runner, not only compile its source.

## Implementation
A CI-only smoke mode is exposed through `STRUCTURALPRO_SMOKE=1`. The normal desktop behavior is unchanged. In smoke mode the Qt event loop is scheduled to exit automatically after initialization.

The Windows smoke workflow installs the canonical runtime requirements and executes `app.main.main()` under this mode.

## Acceptance
- Normal startup remains interactive.
- CI smoke mode initializes the application and exits automatically.
- Windows smoke remains green.
