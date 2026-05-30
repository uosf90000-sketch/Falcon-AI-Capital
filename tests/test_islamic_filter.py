"""Quick unit tests for the Islamic filter (no network needed)."""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from filters.islamic_filter import IslamicFilter, KNOWN_HALAL, KNOWN_HARAM


def test_known_haram_rejected():
    f = IslamicFilter()
    for ticker in ["JPM", "BAC", "PM", "MGM"]:
        result = f.is_halal(ticker)
        assert not result["halal"], f"{ticker} should be haram"
        assert result["status"] == "NON_COMPLIANT"
    print("✓ Known haram stocks correctly rejected")


def test_purification_parser():
    f = IslamicFilter()
    assert f._parse_purification("0%") == 0.0
    assert f._parse_purification("0٪") == 0.0
    assert f._parse_purification("2.5%") == 2.5
    assert f._parse_purification("0.025") == 2.5   # ratio → %
    assert f._parse_purification("٠") == 0.0
    print("✓ Purification rate parser works correctly")


def test_filter_list_removes_haram():
    f = IslamicFilter()
    tickers = ["AAPL", "JPM", "MSFT", "MGM", "NVDA", "PM"]
    # Without API keys, known_haram gets filtered out
    approved = f.filter_list(tickers)
    haram_in_result = set(approved) & KNOWN_HARAM
    assert not haram_in_result, f"Haram stocks passed: {haram_in_result}"
    print(f"✓ filter_list passed: {approved}")


if __name__ == "__main__":
    test_known_haram_rejected()
    test_purification_parser()
    test_filter_list_removed_haram = test_filter_list_removes_haram
    test_filter_list_removed_haram()
    print("\n✅ All tests passed")
