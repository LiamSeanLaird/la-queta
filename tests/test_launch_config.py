"""The editor launch config must start the real app entry point."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_launch_config_runs_make_run_target():
    config = json.loads((ROOT / ".claude" / "launch.json").read_text())
    (entry,) = config["configurations"]
    assert entry["runtimeExecutable"] == "make"
    assert entry["runtimeArgs"] == ["run"]

    makefile = (ROOT / "Makefile").read_text()
    run_recipe = re.search(r"^run:\n\t(.+)$", makefile, re.M)
    assert run_recipe, "Makefile has no run target"
    # The run target starts the wsgi app and honours $(PORT), so the
    # launcher's autoPort (which sets PORT) picks the port.
    assert "--app wsgi" in run_recipe.group(1)
    assert "$(PORT)" in run_recipe.group(1)
    assert (ROOT / "wsgi.py").exists()
    assert re.search(r"^PORT \?= 5001$", makefile, re.M)
    assert entry["port"] == 5001
