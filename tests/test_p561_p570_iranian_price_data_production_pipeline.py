from datetime import date
from decimal import Decimal
import pytest

from core.pricing.iranian_price_data_production_pipeline_v1 import (
    PriceRecord,
    parse_rate,
    price_fingerprint,
    select_effective_price,
    validate_catalog,
)


def _price(code="C01", rate="125000"):
    return PriceRecord(
        item_code=code,
        description="Concrete",
        unit="m3",
        rate=Decimal(rate),
        currency="IRR",
        effective_date=date(2026, 1, 1),
        source_id="OFFICIAL-PRICE-BOOK",
        source_version="2026.1",
        provenance_ref="DOC-001/P12",
    )


def test_fingerprint_is_deterministic():
    assert price_fingerprint(_price()) == price_fingerprint(_price())


def test_catalog_rejects_duplicate_codes():
    with pytest.raises(ValueError):
        validate_catalog((_price(), _price()))


def test_effective_price_selects_latest_supplied_record():
    older = _price(rate="100")
    newer = PriceRecord(**{**older.__dict__, "rate": Decimal("200"), "effective_date": date(2026, 6, 1)})
    result = select_effective_price((older, newer), "C01", date(2026, 7, 1))
    assert result.rate == Decimal("200")


def test_future_price_is_not_selected():
    future = PriceRecord(**{**_price().__dict__, "effective_date": date(2027, 1, 1)})
    with pytest.raises(LookupError):
        select_effective_price((future,), "C01", date(2026, 12, 1))


def test_invalid_currency_fails_closed():
    record = PriceRecord(**{**_price().__dict__, "currency": "USD"})
    with pytest.raises(ValueError):
        validate_catalog((record,))


def test_negative_rate_fails_closed():
    record = PriceRecord(**{**_price().__dict__, "rate": Decimal("-1")})
    with pytest.raises(ValueError):
        validate_catalog((record,))


def test_parse_rate_does_not_apply_conversion():
    assert parse_rate("123.45") == Decimal("123.45")


def test_invalid_rate_fails_closed():
    with pytest.raises(ValueError):
        parse_rate("not-a-rate")
