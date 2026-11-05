"""Public source guards only; native integration is a separate CI build."""
import pytest
from tools.p8p2_patch_r2004_fdl_string32 import patch_spec, TARGET


def test_scoped_patch_preserves_other_versions_and_generic_reader():
    before = 'before\n' + TARGET + '\nafter\n'
    after = patch_spec(before)
    assert after.startswith('before\n') and after.endswith('\nafter\n')
    assert 'dat->from_version == R_2004' in after
    assert '#ifdef IS_DECODER' in after
    assert 'bit_read_T32 (dat)' in after
    assert 'FIELD_VECTOR_T (features, TU32, num_features, 0);' in after
    assert 'DWG_ERR_VALUEOUTOFBOUNDS' in after
    assert 'return 0' not in after


@pytest.mark.parametrize('source', ['', TARGET + TARGET, TARGET.replace('features', 'other')])
def test_patch_rejects_changed_upstream(source):
    with pytest.raises(ValueError):
        patch_spec(source)


def test_patch_rejects_double_application():
    with pytest.raises(ValueError):
        patch_spec(patch_spec(TARGET))
