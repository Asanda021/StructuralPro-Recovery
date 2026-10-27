"""Read quarantined contracts only from a disposable, static-only checkout.

The reviewed quarantine is validated in a zero-active disposable source tree
before making the fixture. No workflow is created in the source checkout and
none of the copied YAML is executed.
"""
import atexit
from functools import lru_cache
from pathlib import Path
import tempfile

from scripts.run_quarantined_workflow_qa import prepare_fixture, current_policy, prepare_source, quarantine_policy

SOURCE_ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _fixture():
    temporary = tempfile.TemporaryDirectory(prefix="structuralpro_static_contract_")
    try:
        disposable = Path(temporary.name)
        source = prepare_source(SOURCE_ROOT, disposable)
        historical = disposable / "historical"
        historical.mkdir()
        checkout = prepare_fixture(source, historical)
    except BaseException:
        temporary.cleanup()
        raise
    atexit.register(temporary.cleanup)
    return checkout, temporary


def historical_root() -> Path:
    # Never let a cached fixture hide changes to the original reviewed bytes.
    quarantine_policy(SOURCE_ROOT)
    checkout, temporary = _fixture()
    # Recheck the isolated zero-active source even when the fixture is cached.
    current_policy(Path(temporary.name) / "source")
    return checkout
