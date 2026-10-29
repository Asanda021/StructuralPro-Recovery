"""Diagnostic pytest probe. Does not enable or disable faulthandler itself."""
import os
import faulthandler
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest
from scripts.diagnose_windows_native_crash import atomic_json

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    expected=os.environ['P6_EXPECT_FAULTHANDLER']=='enabled'
    plugin=item.config.pluginmanager.hasplugin('faulthandler')
    state={'test_started_utc':datetime.now(timezone.utc).isoformat(),
           'test_started_monotonic_ns':time.monotonic_ns(),'expected_enabled':expected,'before_test':faulthandler.is_enabled(),
           'pytest_plugin_present':plugin,'environment_present':'PYTHONFAULTHANDLER' in os.environ,
           'faulthandler_timeout':item.config.getini('faulthandler_timeout') if plugin else None}
    path=Path(os.environ['P6_FH_PROBE']);atomic_json(path,state)
    if plugin and 'P6_EXPECT_DUMP_TIMEOUT' in os.environ:
        assert float(state['faulthandler_timeout'])==float(os.environ['P6_EXPECT_DUMP_TIMEOUT'])
    assert state['before_test']==expected
    assert plugin==expected
    assert state['environment_present']==expected
    yield
    state['test_ended_utc']=datetime.now(timezone.utc).isoformat()
    state['test_ended_monotonic_ns']=time.monotonic_ns()
    state['after_test']=faulthandler.is_enabled();atomic_json(path,state)
    assert state['after_test']==expected
