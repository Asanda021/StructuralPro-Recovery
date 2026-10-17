"""Read quarantined contracts only from a disposable, static-only checkout.

The real repository is validated before making the fixture. No workflow is
created in the source checkout and none of the copied YAML is executed.
"""
import atexit
from functools import lru_cache
from pathlib import Path
import tempfile

from scripts.run_quarantined_workflow_qa import prepare_fixture, current_policy

SOURCE_ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _fixture():
    temporary = tempfile.TemporaryDirectory(prefix="structuralpro_static_contract_")
    try:
        checkout = prepare_fixture(SOURCE_ROOT, Path(temporary.name))
    except BaseException:
        temporary.cleanup()
        raise
    atexit.register(temporary.cleanup)
    return checkout, temporary


def historical_root() -> Path:
    # Recheck source policy even when the temporary fixture is cached.
    current_policy(SOURCE_ROOT)
    return _fixture()[0]
