"""
قائمة الأسهم الشرعية المحلية — بدون API
مصدر البيانات: Musaffa + Zoya (محدّثة يدوياً)

القاعدة: إذا السهم مو في ZERO_PURIFICATION → مرفوض تلقائياً
"""

# ✅ أسهم حلال + تطهير 0% مؤكد
ZERO_PURIFICATION = {
    # ── أمن سيبراني ──────────────────────────────────────────────
    "PANW",   # Palo Alto Networks
    "CRWD",   # CrowdStrike
    "FTNT",   # Fortinet
    "ZS",     # Zscaler
    "OKTA",   # Okta
    "S",      # SentinelOne
    "CYBR",   # CyberArk

    # ── برامج هندسية / EDA ───────────────────────────────────────
    "ANSS",   # Ansys
    "SNPS",   # Synopsys
    "CDNS",   # Cadence
    "PTC",    # PTC Inc

    # ── برامج B2B / SaaS ─────────────────────────────────────────
    "NOW",    # ServiceNow
    "WDAY",   # Workday
    "VEEV",   # Veeva Systems
    "DDOG",   # Datadog
    "MDB",    # MongoDB
    "SNOW",   # Snowflake
    "ZM",     # Zoom
    "TWLO",   # Twilio
    "HUBS",   # HubSpot
    "COUP",   # Coupa Software

    # ── خدمات تقنية ──────────────────────────────────────────────
    "EPAM",   # EPAM Systems
    "GLOB",   # Globant
    "EXLS",   # ExlService
    "PEGA",   # Pegasystems

    # ── رعاية صحية / تقنية طبية ──────────────────────────────────
    "IDXX",   # IDEXX Laboratories
    "PODD",   # Insulet
    "INSP",   # Inspire Medical
    "HOLX",   # Hologic
    "NTRA",   # Natera
    "VERACYTE", # Veracyte
    "IRTC",   # iRhythm
    "AXNX",   # Axonics

    # ── صناعية / أتمتة ───────────────────────────────────────────
    "ROK",    # Rockwell Automation
    "NOVT",   # Novanta
    "ESAB",   # ESAB Corp
    "NDSN",   # Nordson
    "RRX",    # Rexnord

    # ── طاقة متجددة ──────────────────────────────────────────────
    "CWEN",   # Clearway Energy
    "BEP",    # Brookfield Renewable
    "ARRY",   # Array Technologies
    "FLNC",   # Fluence Energy

    # ── مواد / كيمياء متخصصة ─────────────────────────────────────
    "FERG",   # Ferguson
    "AZEK",   # AZEK Company
    "TREX",   # Trex Company
}

# ❌ أسهم حلال لكن بتطهير > 0% — مرفوضة
HAS_PURIFICATION = {
    # تكنولوجيا كبرى (فوائد بنكية على الكاش)
    "AAPL":  1.5,
    "MSFT":  1.2,
    "NVDA":  1.0,
    "GOOGL": 0.8,
    "GOOG":  0.8,
    "AMZN":  0.5,
    "META":  0.4,
    "TSLA":  0.3,
    "NFLX":  0.6,
    "ADBE":  0.7,
    "CRM":   0.5,
    "ORCL":  0.9,
    "QCOM":  0.4,
    "TXN":   0.6,
    "AVGO":  0.3,
    "AMAT":  0.3,
    "LRCX":  0.4,
    "KLAC":  0.3,
    "MCHP":  0.5,
    # رعاية صحية (دخل فوائد)
    "AMGN":  1.1,
    "GILD":  0.8,
    "REGN":  0.5,
    "VRTX":  0.4,
    "BIIB":  0.6,
    "MRNA":  0.3,
    "ILMN":  0.4,
}

# ❌ حرام قطعاً
HARAM = {
    # بنوك
    "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC",
    "TFC", "COF", "AXP", "DFS", "SYF", "ALLY",
    # تأمين
    "MET", "PRU", "AIG", "AFL", "ALL", "CB", "TRV", "PGR",
    # كحول / تبغ
    "PM", "MO", "BTI", "STZ", "BUD", "TAP",
    # قمار
    "MGM", "WYNN", "LVS", "CZR", "PENN", "DKNG",
    # أسلحة
    "LMT", "RTX", "NOC", "GD", "BA",
    # خنزير
    "HRL",
}


def check(ticker: str) -> dict:
    """
    يفحص السهم من القوائم المحلية.

    Returns:
      {
        "decision":  "BUY_ALLOWED" | "SHARIA_REJECTED",
        "reason":    "...",
        "purification": 0.0,
      }
    """
    t = ticker.upper().strip()

    if t in HARAM:
        return {"decision": "SHARIA_REJECTED", "reason": "حرام", "purification": None}

    if t in HAS_PURIFICATION:
        pct = HAS_PURIFICATION[t]
        return {
            "decision": "SHARIA_REJECTED",
            "reason": f"نسبة تطهير {pct}%",
            "purification": pct,
        }

    if t in ZERO_PURIFICATION:
        return {"decision": "BUY_ALLOWED", "reason": "حلال — تطهير 0%", "purification": 0.0}

    # مجهول — نرفضه احتياطاً
    return {
        "decision": "SHARIA_REJECTED",
        "reason": "غير موجود في قائمة الأسهم المعتمدة",
        "purification": None,
    }
