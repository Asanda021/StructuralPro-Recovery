"""An integer CAS revision must not accept Python bool/float equality aliases."""
import pytest

from core.platform.application import StructuralProApp
from test_phase1_cement_render_net_surface_chat import document


@pytest.mark.parametrize("revision", [True, 1.0])
@pytest.mark.parametrize("operation", ["save", "commit"])
def test_aec_revision_type_alias_never_writes_project(tmp_path, revision, operation):
    app = StructuralProApp(tmp_path)
    try:
        app.create_project("Synthetic CAS type regression", "P")
        draft = document()
        app.save_aec_system_draft("P", draft, expected_revision=0)
        digest = app.store.current_digest("P")
        before = app.open_project("P")
        with pytest.raises((ValueError, RuntimeError)):
            if operation == "save":
                app.save_aec_system_draft("P", draft, expected_revision=revision)
            else:
                app.commit_aec_system("P", "cement_render", "L1", "WALL-RENDER-1",
                                      expected_revision=revision)
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()
