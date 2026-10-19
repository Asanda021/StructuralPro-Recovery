"""Finite and exact integer numerical gates of reviewed AEC domain inputs."""
import pytest
from core.takeoff.reviewed_components import positive

@pytest.mark.parametrize('v', ['9007199254740993','1.25','9999999999999999999999999'])
def test_explicit_counts_not_rounded(v):
    with pytest.raises(ValueError): positive(v,'count',integer=True)

@pytest.mark.parametrize('v', ['1e-400','-1e-400'])
def test_nonzero_cannot_be_zero(v):
    with pytest.raises(ValueError): positive(v,'length',allow_zero=True)

def test_real_zero_is_permitted():
    assert positive('0e-1000','opening',allow_zero=True)==0.0

@pytest.mark.parametrize('v', ['2','2.0',3])
def test_existing_counts_accepted(v):
    assert positive(v,'count',integer=True)==float(v)
