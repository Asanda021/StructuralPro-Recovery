from pathlib import Path
import multiprocessing
import pytest
from core.platform.application import StructuralProApp
from core.projects.store import ProjectStore


@pytest.mark.parametrize('operation', ['estimate', 'snapshot', 'audit', 'report'])
def test_stale_desktop_does_not_erase_external_takeoff(tmp_path, operation):
    writer = StructuralProApp(tmp_path)
    writer.create_project('پروژه ایمن', 'p')
    stale = StructuralProApp(tmp_path)
    stale.open_project('p')
    if operation == 'audit':
        from PySide6.QtWidgets import QApplication
        from app.manual_takeoff import ManualTakeoffDialog
        qt = QApplication.instance() or QApplication([])
        dialog = ManualTakeoffDialog(stale, 'p')
    writer.add_takeoff('p', 'building', 'slab_volume', length=2, width=2,
                       thickness=1, source_id='external')
    if operation == 'estimate':
        stale.recalculate_estimate('p')
    elif operation == 'snapshot':
        stale.build_commercial_snapshot('p')
    elif operation == 'audit':
        dialog._audit('review', {'event': 'review'})
        dialog.close()
    else:
        stale.recalculate_estimate('p')
        stale.report('p', 'xlsx', tmp_path / 'report.xlsx')
    writer.store.close()
    stale.store.close()
    reopened = StructuralProApp(tmp_path)
    assert [r['source_id'] for r in reopened.open_project('p')['takeoffs']] == ['external']
    assert reopened.store.integrity_check()['ok']
    reopened.store.close()


def test_cache_observes_other_connection_commit(tmp_path):
    first = ProjectStore(tmp_path / 'db.sqlite')
    first.save('p', {'id': 'p', 'name': 'اول'})
    other = ProjectStore(first.path)
    old = other.get('p')
    new = first.get('p')
    new['name'] = 'جدید'
    first.save('p', new)
    assert other.get('p')['name'] == 'جدید'
    # Refreshing the cache must not authorize an older detached snapshot.
    with pytest.raises(RuntimeError, match='changed since write began'):
        other.save('p', old)
    assert other.get('p')['name'] == 'جدید'
    assert not other.db.in_transaction
    assert len(other.revisions('p')) == 2
    first.close()
    other.close()


def _stale_estimator(directory, ready, written):
    app = StructuralProApp(directory)
    app.open_project('p')
    ready.set()
    assert written.wait(15)
    app.recalculate_estimate('p')
    app.store.close()


def test_spawned_estimator_preserves_another_process_takeoff(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project('دو پردازش', 'p')
    ctx = multiprocessing.get_context('spawn')
    ready, written = ctx.Event(), ctx.Event()
    child = ctx.Process(target=_stale_estimator, args=(str(tmp_path), ready, written))
    child.start()
    assert ready.wait(15)
    app.add_takeoff('p', 'building', 'slab_volume', length=2, width=2,
                    thickness=1, source_id='process-source')
    written.set()
    child.join(20)
    assert child.exitcode == 0
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    assert [r['source_id'] for r in reopened.open_project('p')['takeoffs']] == ['process-source']
    reopened.store.close()
