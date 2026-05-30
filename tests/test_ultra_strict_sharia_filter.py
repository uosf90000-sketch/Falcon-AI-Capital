"""
اختبارات وحدة Ultra Strict Sharia Filter
لا تحتاج شبكة — تستخدم Mock لـ Zoya و Fltrna.
"""

import sys
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from filters.ultra_strict_sharia_filter import (
    UltraStrictShariaFilter,
    KNOWN_HARAM,
    HALAL_WITH_PURIFICATION,
    _parse_purification,
)


import shutil

def _make_filter():
    f = UltraStrictShariaFilter(
        zoya_api_key="test_zoya_key",
        fltrna_api_key="test_fltrna_key",
    )
    # اجعل الكاش معطّلاً في الاختبارات بمسح مجلده
    shutil.rmtree(f.CACHE_DIR, ignore_errors=True)
    f.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return f


def _zoya_resp(status="COMPLIANT", purification_ratio=0.0):
    """Mock Zoya GraphQL response."""
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "data": {
            "stockReport": {
                "ticker": "TEST",
                "complianceStatus": status,
                "purificationRatio": purification_ratio,
                "businessSector": "Technology",
            }
        }
    }
    return mock


def _fltrna_resp(purification_ratio=0.0, status_code=200):
    """Mock Fltrna REST response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"purificationRatio": purification_ratio}
    return mock


# ── 1. رفض مباشر من القائمة المحلية ──────────────────────────────────────────

def test_known_haram_rejected_without_api():
    f = _make_filter()
    for ticker in ["JPM", "BAC", "PM", "MGM", "LMT", "HRL"]:
        r = f.check(ticker)
        assert r["decision"] == "SHARIA_REJECTED", f"{ticker} يجب رفضه"
        assert r["rejection_code"] == "KNOWN_HARAM"
        assert not r["buy_allowed"]
    print("✓ KNOWN_HARAM → SHARIA_REJECTED (بدون API)")


def test_halal_with_purification_rejected_without_api():
    f = _make_filter()
    for ticker in ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA", "META"]:
        r = f.check(ticker)
        assert r["decision"] == "SHARIA_REJECTED", f"{ticker} يجب رفضه"
        assert r["rejection_code"] == "HAS_PURIFICATION"
        assert not r["buy_allowed"]
    print("✓ HALAL_WITH_PURIFICATION → SHARIA_REJECTED (بدون API)")


# ── 2. بيانات مفقودة → SHARIA_REJECTED ──────────────────────────────────────

def test_zoya_missing_data_rejected():
    f = _make_filter()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": {"stockReport": None}}

    with patch.object(f._session, "post", return_value=mock_resp):
        r = f.check("PANW")
    assert r["decision"] == "SHARIA_REJECTED"
    assert r["rejection_code"] == "ZOYA_DATA_MISSING"
    print("✓ Zoya data missing → SHARIA_REJECTED")


def test_fltrna_missing_data_rejected():
    f = _make_filter()

    with patch.object(f._session, "post", return_value=_zoya_resp()):
        fltrna_mock = MagicMock()
        fltrna_mock.status_code = 404
        fltrna_mock.raise_for_status = MagicMock()
        with patch.object(f._session, "get", return_value=fltrna_mock):
            r = f.check("PANW")

    assert r["decision"] == "SHARIA_REJECTED"
    assert r["rejection_code"] == "FLTRNA_DATA_MISSING"
    print("✓ Fltrna data missing (404) → SHARIA_REJECTED")


def test_zoya_api_error_rejected():
    f = _make_filter()
    with patch.object(f._session, "post", side_effect=Exception("timeout")):
        r = f.check("CRWD")
    assert r["decision"] == "SHARIA_REJECTED"
    assert r["rejection_code"] == "ZOYA_DATA_MISSING"
    print("✓ Zoya API error → SHARIA_REJECTED")


def test_fltrna_api_error_rejected():
    f = _make_filter()
    with patch.object(f._session, "post", return_value=_zoya_resp()):
        with patch.object(f._session, "get", side_effect=Exception("timeout")):
            r = f.check("CRWD")
    assert r["decision"] == "SHARIA_REJECTED"
    assert r["rejection_code"] == "FLTRNA_DATA_MISSING"
    print("✓ Fltrna API error → SHARIA_REJECTED")


# ── 3. Zoya غير COMPLIANT → SHARIA_REJECTED ──────────────────────────────────

def test_zoya_non_compliant_rejected():
    f = _make_filter()
    for status in ["NON_COMPLIANT", "DOUBTFUL", "QUESTIONABLE", "HARAM"]:
        with patch.object(f._session, "post", return_value=_zoya_resp(status=status)):
            r = f.check("XYZ")
        assert r["decision"] == "SHARIA_REJECTED", f"status={status} يجب رفضه"
        assert r["rejection_code"] == "ZOYA_NOT_COMPLIANT"
    print("✓ Zoya non-COMPLIANT → SHARIA_REJECTED")


# ── 4. Zoya purification > 0% → SHARIA_REJECTED ──────────────────────────────

def test_zoya_purification_nonzero_rejected():
    f = _make_filter()
    for ratio in [0.001, 0.005, 0.01, 0.015]:  # 0.1%, 0.5%, 1%, 1.5%
        with patch.object(f._session, "post", return_value=_zoya_resp(purification_ratio=ratio)):
            r = f.check("SOMESTOCK")
        assert r["decision"] == "SHARIA_REJECTED", f"ratio={ratio} يجب رفضه"
        assert r["rejection_code"] == "ZOYA_PURIFICATION_NONZERO"
        assert r["zoya_purification"] > 0
    print("✓ Zoya purification > 0% → SHARIA_REJECTED")


# ── 5. Fltrna purification > 0% → SHARIA_REJECTED ────────────────────────────

def test_fltrna_purification_nonzero_rejected():
    f = _make_filter()
    with patch.object(f._session, "post", return_value=_zoya_resp()):
        with patch.object(f._session, "get", return_value=_fltrna_resp(purification_ratio=0.005)):
            r = f.check("PANW")
    assert r["decision"] == "SHARIA_REJECTED"
    assert r["rejection_code"] == "FLTRNA_PURIFICATION_NONZERO"
    assert r["fltrna_purification"] > 0
    print("✓ Fltrna purification > 0% → SHARIA_REJECTED")


# ── 6. تعارض بين المصدرين → SHARIA_REJECTED ─────────────────────────────────

def test_source_disagreement_rejected():
    """Zoya=0% لكن Fltrna=0.5% — تعارض → رفض."""
    f = _make_filter()
    with patch.object(f._session, "post", return_value=_zoya_resp(purification_ratio=0.0)):
        with patch.object(f._session, "get", return_value=_fltrna_resp(purification_ratio=0.005)):
            r = f.check("PANW")
    assert r["decision"] == "SHARIA_REJECTED"
    assert r["rejection_code"] in ("FLTRNA_PURIFICATION_NONZERO", "SOURCE_DISAGREEMENT")
    print("✓ Source disagreement → SHARIA_REJECTED")


# ── 7. جميع الشروط متحققة → BUY_ALLOWED ─────────────────────────────────────

def test_all_conditions_met_buy_allowed():
    """Zoya=COMPLIANT+0%, Fltrna=0% → BUY_ALLOWED."""
    f = _make_filter()
    with patch.object(f._session, "post", return_value=_zoya_resp(status="COMPLIANT", purification_ratio=0.0)):
        with patch.object(f._session, "get", return_value=_fltrna_resp(purification_ratio=0.0)):
            r = f.check("PANW")
    assert r["decision"] == "BUY_ALLOWED", f"يجب أن يكون BUY_ALLOWED — {r}"
    assert r["buy_allowed"] is True
    assert r["zoya_status"] == "COMPLIANT"
    assert r["zoya_purification"] == 0.0
    assert r["fltrna_purification"] == 0.0
    assert r["sources_agree"] is True
    assert r["rejection_reason"] == ""
    print("✓ جميع الشروط متحققة → BUY_ALLOWED")


def test_buy_allowed_multiple_tickers():
    """يفحص قائمة أسهم ويسمح فقط بالمستوفية."""
    f = _make_filter()
    with patch.object(f._session, "post", return_value=_zoya_resp(status="COMPLIANT", purification_ratio=0.0)):
        with patch.object(f._session, "get", return_value=_fltrna_resp(purification_ratio=0.0)):
            allowed = f.filter_buy_allowed(["PANW", "CRWD", "FTNT"])
    assert set(allowed) == {"PANW", "CRWD", "FTNT"}
    print(f"✓ filter_buy_allowed: {allowed}")


# ── 8. محلل نسبة التطهير ─────────────────────────────────────────────────────

def test_parse_purification():
    assert _parse_purification("0%") == 0.0
    assert _parse_purification("0٪") == 0.0
    assert _parse_purification("0") == 0.0
    assert _parse_purification("") == 0.0
    assert _parse_purification("1.5%") == 1.5
    assert _parse_purification("0.015") == 1.5     # عشري → مئوي
    assert _parse_purification("0.005") == 0.5
    print("✓ _parse_purification يعمل صح")


# ── 9. مفاتيح API إلزامية ────────────────────────────────────────────────────

def test_api_keys_required():
    try:
        UltraStrictShariaFilter(zoya_api_key="", fltrna_api_key="x")
        assert False, "يجب رفع ValueError"
    except ValueError as e:
        assert "zoya" in str(e).lower() or "Zoya" in str(e)

    try:
        UltraStrictShariaFilter(zoya_api_key="x", fltrna_api_key="")
        assert False, "يجب رفع ValueError"
    except ValueError as e:
        assert "fltrna" in str(e).lower() or "Fltrna" in str(e)
    print("✓ API keys إلزامية — ValueError عند الغياب")


# ── 10. هيكل النتيجة ─────────────────────────────────────────────────────────

def test_result_structure_buy_allowed():
    f = _make_filter()
    with patch.object(f._session, "post", return_value=_zoya_resp()):
        with patch.object(f._session, "get", return_value=_fltrna_resp()):
            r = f.check("PANW")
    required_keys = {
        "ticker", "decision", "buy_allowed", "rejection_reason",
        "rejection_code", "zoya_status", "zoya_purification",
        "fltrna_purification", "sources_agree",
    }
    assert required_keys.issubset(r.keys()), f"مفاتيح مفقودة: {required_keys - r.keys()}"
    assert r["decision"] in ("BUY_ALLOWED", "SHARIA_REJECTED")
    print("✓ هيكل النتيجة صحيح")


def test_result_structure_rejected():
    f = _make_filter()
    r = f.check("JPM")  # known haram, no API needed
    required_keys = {
        "ticker", "decision", "buy_allowed", "rejection_reason",
        "rejection_code", "zoya_status", "zoya_purification",
        "fltrna_purification", "sources_agree",
    }
    assert required_keys.issubset(r.keys())
    assert r["decision"] == "SHARIA_REJECTED"
    assert r["buy_allowed"] is False
    assert r["rejection_reason"] != ""
    print("✓ هيكل نتيجة الرفض صحيح")


if __name__ == "__main__":
    test_known_haram_rejected_without_api()
    test_halal_with_purification_rejected_without_api()
    test_zoya_missing_data_rejected()
    test_fltrna_missing_data_rejected()
    test_zoya_api_error_rejected()
    test_fltrna_api_error_rejected()
    test_zoya_non_compliant_rejected()
    test_zoya_purification_nonzero_rejected()
    test_fltrna_purification_nonzero_rejected()
    test_source_disagreement_rejected()
    test_all_conditions_met_buy_allowed()
    test_buy_allowed_multiple_tickers()
    test_parse_purification()
    test_api_keys_required()
    test_result_structure_buy_allowed()
    test_result_structure_rejected()
    print("\n✅ جميع اختبارات Ultra Strict Sharia Filter نجحت")
