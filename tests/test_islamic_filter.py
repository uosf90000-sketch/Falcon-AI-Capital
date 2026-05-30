"""اختبارات وحدة فلتر الأسهم الإسلامية — لا تحتاج شبكة."""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from filters.islamic_filter import (
    IslamicFilter, KNOWN_HARAM, HALAL_WITH_PURIFICATION, LIKELY_HALAL_ZERO
)


def test_haram_rejected():
    f = IslamicFilter()
    for ticker in ["JPM", "BAC", "PM", "MGM", "LMT"]:
        r = f.is_halal(ticker)
        assert not r["halal"], f"{ticker} يجب أن يُرفض"
        assert r["status"] == "NON_COMPLIANT"
    print("✓ الأسهم الحرام مرفوضة")


def test_halal_with_purification_rejected():
    """AAPL, NVDA حلال لكن فيها تطهير — يجب رفضها."""
    f = IslamicFilter()
    for ticker in ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA"]:
        r = f.is_halal(ticker)
        assert not r["halal"], f"{ticker} يجب رفضه لوجود تطهير"
        assert "تطهير" in r["reason"] or r["source"] == "halal_with_purification"
    print("✓ الأسهم الحلال ذات التطهير مرفوضة")


def test_purification_parser():
    f = IslamicFilter()
    assert f._parse_purification("0%") == 0.0
    assert f._parse_purification("0٪") == 0.0
    assert f._parse_purification("1.5%") == 1.5
    assert f._parse_purification("0.015") == 1.5   # نسبة عشرية → مئوية
    assert f._parse_purification("0") == 0.0
    assert f._parse_purification("") == 0.0
    print("✓ محلل نسبة التطهير يعمل صح")


def test_filter_list_removes_haram_and_purification():
    f = IslamicFilter()
    tickers = ["AAPL", "JPM", "PANW", "NVDA", "MGM", "CRWD"]
    approved = f.filter_list(tickers)

    # لا يجوز أن يمر حرام أو صاحب تطهير
    bad = set(approved) & (KNOWN_HARAM | HALAL_WITH_PURIFICATION)
    assert not bad, f"أسهم ممنوعة مرت: {bad}"

    # PANW و CRWD من LIKELY_HALAL_ZERO — لكن بدون API ستُرفض احتياطاً
    # (لأن _check_sector يرجع None للأسهم المجهولة)
    print(f"✓ filter_list نتيجة: {approved}")


def test_reject_structure():
    f = IslamicFilter()
    r = f._reject("TEST", "test", "سبب الرفض")
    assert r["halal"] is False
    assert r["purification_rate"] == 0.0
    assert r["status"] == "NON_COMPLIANT"
    print("✓ هيكل الرفض صحيح")


if __name__ == "__main__":
    test_haram_rejected()
    test_halal_with_purification_rejected()
    test_purification_parser()
    test_filter_list_removes_haram_and_purification()
    test_reject_structure()
    print("\n✅ جميع الاختبارات نجحت")
