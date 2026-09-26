"""
Entity extraction (phones, UPI IDs, amounts, links) and offline link checks.

The link checks here run with no network access so the demo works anywhere.
In production, add: domain age (WHOIS/RDAP), Google Safe Browsing, redirect
expansion for short links, and your own reported-URL table.
"""
import re
from urllib.parse import urlparse

# Official domains per brand keyword. Keep this list maintained and reviewed;
# Indian banks are migrating to *.bank.in, so both old and new domains appear.
OFFICIAL_DOMAINS = {
    "sbi": ["sbi.co.in", "onlinesbi.sbi", "sbi.bank.in", "sbicard.com"],
    "hdfc": ["hdfcbank.com", "hdfc.bank.in", "hdfc.com", "hdfclife.com"],
    "icici": ["icicibank.com", "icici.bank.in"],
    "axis": ["axisbank.com", "axis.bank.in"],
    "kotak": ["kotak.com", "kotak.bank.in"],
    "pnb": ["pnbindia.in", "pnb.bank.in"],
    "baroda": ["bankofbaroda.in", "bankofbaroda.bank.in"],
    "canara": ["canarabank.com", "canarabank.bank.in"],
    "paytm": ["paytm.com"],
    "phonepe": ["phonepe.com"],
    "npci": ["npci.org.in"],
    "bhim": ["bhimupi.org.in"],
    "uidai": ["uidai.gov.in"],
    "aadhaar": ["uidai.gov.in"],
    "aadhar": ["uidai.gov.in"],
    "incometax": ["incometax.gov.in"],
    "epfo": ["epfindia.gov.in"],
    "irctc": ["irctc.co.in"],
    "indiapost": ["indiapost.gov.in"],
    "mahavitaran": ["mahadiscom.in"],
    "mahadiscom": ["mahadiscom.in"],
    "msedcl": ["mahadiscom.in"],
    "amazon": ["amazon.in", "amazon.com"],
    "flipkart": ["flipkart.com"],
    "jio": ["jio.com"],
    "airtel": ["airtel.in"],
    "fedex": ["fedex.com"],
    "bluedart": ["bluedart.com"],
    "dhl": ["dhl.com", "dhl.co.in"],
    "whatsapp": ["whatsapp.com"],
    "rbi": ["rbi.org.in"],
    "trai": ["trai.gov.in"],
    "cybercrime": ["cybercrime.gov.in"],
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "cutt.ly", "is.gd", "t.ly", "rb.gy", "shorturl.at",
    "tiny.cc", "ow.ly", "t.co", "rebrand.ly", "s.id", "shorturl.asia", "v.gd",
}

SUSPICIOUS_TLDS = {
    "xyz", "top", "click", "live", "buzz", "icu", "online", "site", "shop", "vip",
    "tk", "ml", "ga", "cf", "gq", "cc", "rest", "sbs", "cfd", "work", "support",
}

LURE_WORDS = ("kyc", "update", "verify", "secure", "login", "reward", "refund",
              "claim", "bonus", "blocked", "helpdesk", "customer-care", "billpay")

URL_RE = re.compile(
    r"(?<![@\w.])((?:https?://|www\.)[^\s<>\"']+|[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9-]{1,62})*"
    r"\.(?:com|in|net|org|xyz|top|info|online|site|live|click|buzz|icu|shop|co|me|io|app|link|ly|gl|at|gd|vip|cc|tk|ml|ga|cf|gq|sbi|sbs|cfd)"
    r"(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?([6-9]\d{4})[\s-]?(\d{5})(?!\d)")
UPI_RE = re.compile(r"(?<![\w.])([a-z0-9][a-z0-9.\-_]{1,255}@[a-z]{2,64})(?![\w.])", re.IGNORECASE)
AMOUNT_RE = re.compile(r"(?:₹|\brs\.?|\binr)\s?(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*)\s?(?:रुपये|रुपए|rupees)", re.IGNORECASE)


def _host(url: str) -> str:
    u = url if url.lower().startswith(("http://", "https://")) else "http://" + url
    try:
        host = (urlparse(u).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _matches_official(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def check_link(url: str) -> dict:
    """Return {'url','host','flags':[signal ids]} for one link."""
    url = url.rstrip(".,;:!?)")
    host = _host(url)
    flags = []
    if not host:
        return {"url": url, "host": host, "flags": flags}

    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host) or host.startswith("xn--") or ".xn--" in host:
        flags.append("suspicious_link")
    if host in SHORTENERS:
        flags.append("short_link")
    if urlparse(url if "://" in url else "http://" + url).path.lower().endswith(".apk"):
        flags.append("apk_link")

    compact = host.replace("-", "").replace(".", "")
    for brand, domains in OFFICIAL_DOMAINS.items():
        if brand in compact and not _matches_official(host, domains):
            flags.append("fake_brand_link")
            break
    if "gov" in host and not (host.endswith(".gov.in") or host.endswith(".nic.in")):
        flags.append("fake_brand_link")

    tld = host.rsplit(".", 1)[-1]
    if tld in SUSPICIOUS_TLDS:
        flags.append("suspicious_link")
    if host.count("-") >= 2 or any(w in host for w in LURE_WORDS):
        if not any(_matches_official(host, d) for d in OFFICIAL_DOMAINS.values()):
            flags.append("suspicious_link")

    return {"url": url, "host": host, "flags": sorted(set(flags))}


def extract(text: str) -> dict:
    text = text or ""
    links = [check_link(m.group(1)) for m in URL_RE.finditer(text)]
    phones = sorted({a + b for a, b in PHONE_RE.findall(text)})
    upis = sorted({u.lower() for u in UPI_RE.findall(text)})
    amounts = []
    for m in AMOUNT_RE.finditer(text):
        raw = m.group(1) or m.group(2)
        if raw:
            amounts.append(raw.replace(",", ""))
    return {"links": links, "phones": phones, "upi_ids": upis, "amounts": amounts}


def entity_signals(entities: dict) -> set:
    s = set()
    for link in entities["links"]:
        s.add("has_link")
        s.update(link["flags"])
    if entities["phones"]:
        s.add("has_phone")
    if entities["upi_ids"]:
        s.add("has_upi")
    if entities["amounts"]:
        s.add("has_amount")
    return s


def entity_keys(entities: dict) -> list:
    """Normalised keys used for the community 'reported' table."""
    keys = [("phone", p) for p in entities["phones"]]
    keys += [("upi", u) for u in entities["upi_ids"]]
    keys += [("host", l["host"]) for l in entities["links"]
             if l["host"] and not any(_matches_official(l["host"], d) for d in OFFICIAL_DOMAINS.values())]
    return keys


def mask(value: str, kind: str) -> str:
    """Mask entities for the family dashboard so full numbers aren't exposed."""
    if kind == "phone" and len(value) >= 10:
        return value[:2] + "xxxxx" + value[-3:]
    if kind == "upi" and "@" in value:
        name, bank = value.split("@", 1)
        return name[:2] + "***@" + bank
    return value
