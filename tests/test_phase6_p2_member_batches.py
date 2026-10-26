"""Native IFC4 member-by-member progress and mid-parse cancellation, no fake success."""
import threading
import pytest


def test_real_ifc_native_progress_reports_validated_member_batches(tmp_path):
    from test_phase2_priority5_ifc import model_file
    from core.bim.ifc import DeepIFCAdapter
    path=tmp_path/'real-progress.ifc'
    model, expected=model_file(path)
    progress=[]
    doc=DeepIFCAdapter().read_display_contract(
        path,revision='R1',max_triangles=40000,
        batch_size=3,on_progress=lambda done,total:progress.append((done,total)))
    assert progress == [(3,12),(6,12),(9,12),(12,12)]
    assert len(doc['elements'])==len(expected)==12
    assert not doc['omitted_ids']
    assert doc['quantity_authority'] is False


def test_cancel_during_actual_member_processing_keeps_no_committed_scene(tmp_path):
    from test_phase2_priority5_ifc import model_file
    from core.bim.ifc import DeepIFCAdapter
    path=tmp_path/'cancel-progress.ifc'
    model_file(path)
    stop=threading.Event()
    batches=[]
    def cancel_after_batch(done,total):
        batches.append(done)
        stop.set()
    with pytest.raises(InterruptedError, match='لغو'):
        DeepIFCAdapter().read_display_contract(
            path,revision='R1',max_triangles=40000,batch_size=2,
            cancel_event=stop,on_progress=cancel_after_batch)
    assert batches==[2]


def test_invalid_ifc_worker_batch_size_denied(tmp_path):
    from test_phase2_priority5_ifc import model_file
    from core.bim.ifc import DeepIFCAdapter
    path=tmp_path/'invalid-batch.ifc'
    model_file(path)
    with pytest.raises(ValueError, match='بسته'):
        DeepIFCAdapter().read_display_meshes(path,batch_size=0)
