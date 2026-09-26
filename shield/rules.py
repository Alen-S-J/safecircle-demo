"""
Rules engine: atomic signals + scam playbooks.

Signals are small, explainable facts ("asks for money", "claims to be police").
Playbooks combine signals into a scam category with a risk FLOOR. The LLM can
raise risk above a rule's floor but can never lower it.

Patterns cover English, Hinglish (Latin script), Hindi and Marathi (Devanagari).
Note: \b word boundaries are unreliable around Devanagari vowel signs, so the
Devanagari patterns deliberately avoid them.
"""
import re

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _p(*patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


SIGNAL_PATTERNS = {
    "otp_request": _p(
        r"(share|send|tell|give|forward|read out|batao|bata do|bhejo|बताएं|बताइए|बताओ|भेजें|भेजो|सांगा|पाठवा).{0,40}(otp|o\.t\.p|one[- ]time password|verification code|\bcode\b|ओटीपी|कोड)",
        r"(otp|one[- ]time password|verification code|ओटीपी).{0,40}(share|send|tell|batao|bata|bhejo|बताएं|बताइए|बताओ|भेजें|सांगा|पाठवा)",
    ),
    "money_request": _p(
        r"\b(send|transfer|pay|deposit|lend)\b.{0,40}(money|₹|rs\.?|inr|rupees|amount|\d{3,})",
        r"(₹|\brs\.?|\binr)\s?\d[\d,]*.{0,40}\b(send|transfer|pay|deposit|urgently|needed|need)\b",
        r"\b(need|needs|require)\b.{0,30}(₹|\brs\.?|money|rupees|\d{4,})",
        r"(paise|paisa|rupay|rupaye).{0,20}(bhejo|bhej do|chahiye|transfer)",
        r"(पैसे|पैसा|रुपये|रुपए|₹).{0,30}(भेज|ट्रांसफर|ट्रान्सफर|चाहिए|पाठव|हवे|जमा)",
        r"\b(processing|registration|release|clearance|customs|security|verification)\s+(fee|charge|charges|amount|deposit)",
        r"\b(prepaid task|pay to start|joining fee)\b",
        r"(प्रोसेसिंग फीस|प्रोसेसिंग फ़ीस|रजिस्ट्रेशन फीस|शुल्क जमा)",
    ),
    "urgency": _p(
        r"\b(urgent(ly)?|immediately|right now|asap|within \d+ (hours?|minutes?|mins?)|today itself|last (chance|warning|reminder)|expires? today|tonight|limited seats|register now)\b",
        r"\b(jaldi|turant|abhi ke abhi|aaj hi)\b",
        r"(तुरंत|जल्दी|अभी|आज ही|फ़ौरन|फौरन|लगेच|ताबडतोब|आजच|त्वरित|आज रात्री)",
    ),
    "new_number": _p(
        r"\b(new number|changed my number|number (has )?changed|lost my phone|phone (fell|is lost|got lost|is broken|was stolen|broke)|my old (phone|number))\b",
        r"(naya number|mera phone kho|phone kho gaya|phone toot)",
        r"(नया नंबर|नंबर बदल|फ़ोन खो|फोन खो|नवीन नंबर|फोन हरवला|नंबर बदलला)",
    ),
    "family_claim": _p(
        r"\b(hi|hello|hey)\s+(mom|mum|dad|papa|mummy|maa|amma|appa|aai|baba)\b",
        r"\b(it'?s|this is) (your|ur) (son|daughter|grandson|granddaughter|beta|beti)\b",
        r"\bthis is (rahul|your son|your daughter)\b",
        r"(मैं तुम्हारा बेटा|मैं आपका बेटा|आपकी बेटी|मी तुमचा मुलगा|मी तुमची मुलगी|हाय मम्मी|हाय पापा|आई,|बाबा,)",
    ),
    "secrecy": _p(
        r"\b(don'?t|do not|dont) (tell|inform) (anyone|anybody|dad|mom|mummy|papa|family|your family)\b",
        r"\b(keep (this|it) (secret|confidential|between us)|strictly confidential)\b",
        r"(kisi ko mat batana|kisi ko na batana)",
        r"(किसी को मत बताना|किसी को न बताएं|किसी को ना बताना|गोपनीय रखें|कोणालाही सांगू नका|कुणाला सांगू नको)",
    ),
    "authority_police": _p(
        r"\b(police|cbi|narcotics|ncb|enforcement directorate|cyber ?crime (branch|cell|department)|crime branch|customs (officer|department)|trai officer|rbi officer)\b",
        r"(पुलिस|पोलीस|सीबीआई|नारकोटिक्स|क्राइम ब्रांच|कस्टम्स|साइबर क्राइम|सायबर क्राइम)",
    ),
    "arrest_threat": _p(
        r"\b(arrest(ed)?|digital arrest|warrant|fir (has been|is) (filed|registered)|legal action|money laundering|jail)\b",
        r"(गिरफ्तार|गिरफ़्तार|अटक|वारंट|जेल|मनी लॉन्ड्रिंग|कानूनी कार्रवाई|कायदेशीर कारवाई)",
    ),
    "video_call_demand": _p(
        r"\b(video call|skype|stay on (the )?(call|line|camera)|don'?t (disconnect|cut) the call|keep (your )?camera on)\b",
        r"(वीडियो कॉल|व्हिडिओ कॉल|कॉल मत काटना|कॉल कट करू नका)",
    ),
    "parcel": _p(
        r"\b(parcel|courier|fedex|dhl|blue ?dart|consignment|shipment)\b",
        r"(पार्सल|कूरियर|कुरिअर)",
    ),
    "bank_impersonation": _p(
        r"\b(sbi|hdfc|icici|axis bank|kotak|pnb|bank of baroda|canara|yes bank|union bank|bank'?s?)\b",
        r"(बैंक|बँक)",
    ),
    "account_threat": _p(
        r"\b(account|a/c|card|sim|pan|aadhaa?r|kyc)\b.{0,40}\b(block(ed)?|suspend(ed)?|clos(e|ed)|freez(e|ed)|frozen|deactivat(e|ed)|expired?|disabled)\b",
        r"\b(kyc|pan|aadhaa?r)\b.{0,30}\b(update|verify|verification|pending|expired)\b",
        r"(खाता|खाते|अकाउंट|कार्ड|केवायसी|kyc).{0,30}(बंद|ब्लॉक|निलंबित|फ्रीज|अपडेट)",
    ),
    "utility_cut": _p(
        r"\b(electricity|power|light|bijli|gas)\b.{0,40}\b(disconnect(ed|ion)?|cut|discontinued)\b",
        r"\b(disconnect(ed|ion)?)\b.{0,40}\b(electricity|power|tonight|today)\b",
        r"(बिजली|वीज|लाइट).{0,40}(कट|काट|बंद|खंडित)",
    ),
    "remote_app": _p(
        r"\b(anydesk|any desk|teamviewer|team viewer|quick ?support|rustdesk|airdroid|screen ?shar(e|ing)|remote access)\b",
        r"\b(install|download)\b.{0,30}\bapk\b",
        r"(स्क्रीन शेयर|स्क्रीन शेअर|एनीडेस्क)",
    ),
    "prize": _p(
        r"\b(you (have )?won|winner|lottery|lucky draw|jackpot|kbc|kaun banega crorepati|prize money)\b",
        r"(लॉटरी|इनाम|जीत गए|जीते हैं|बक्षीस|लकी ड्रॉ|केबीसी)",
    ),
    "investment_returns": _p(
        r"\b(guaranteed (returns?|profits?)|double your (money|investment)|\d+\s?% (daily|weekly|monthly|per day|per week|per month)|risk[- ]free (returns?|profit|investment)|assured returns?|stock tips?|ipo allotment|vip (trading )?group|trading group|crypto(currency)?|bitcoin|usdt)\b",
        r"(पक्का मुनाफ़ा|पक्का मुनाफा|दोगुना|गारंटीड रिटर्न|खात्रीशीर परतावा|दुप्पट)",
    ),
    "job_task": _p(
        r"\b(part[- ]time (job|work)|work from home|like (youtube )?videos|rate (hotels|products|restaurants)|daily (income|earning)|prepaid task|telegram task)\b",
        r"\bearn\b.{0,15}(₹|\brs\.?)?\s?\d[\d,]*\s*(per day|daily|a day|/day)",
        r"(घर बैठे कमाई|पार्ट टाइम|रोज़ कमाएं|रोज कमाएं|घरबसल्या)",
    ),
    "refund": _p(
        r"\b(refund|cashback|cash back|claim your (money|amount|reward))\b",
        r"(रिफंड|रिफ़ंड|कैशबैक|परतावा)",
    ),
    "emotional_bond": _p(
        r"\b(only (person|one) i (can )?trust|i love you|my love|my dear|thinking (about|of) you (every|all)|soul ?mate|god (has )?brought us|you mean (so much|everything))\b",
        r"(मेरी जान|सिर्फ़ तुम पर भरोसा|सिर्फ तुम पर भरोसा|माझा विश्वास फक्त)",
    ),
    "hardship_story": _p(
        r"\b(hospital|accident|surgery|stuck at (the )?(airport|customs|border)|medical emergency|stranded)\b",
        r"(अस्पताल|हॉस्पिटल|एक्सीडेंट|दुर्घटना|रुग्णालय|अपघात|इमरजेंसी)",
    ),
    "upi_collect": _p(
        r"\b(enter|put|type) (your )?(upi )?pin\b.{0,40}\b(receive|get|credit|refund|cashback)",
        r"\b(receive|get|credit)\b.{0,40}\b(enter|put|type) (your )?(upi )?pin\b",
        r"\b(approve|accept) (the |this )?(collect )?(request|payment request)\b",
        r"\bscan (this|the) qr.{0,30}(receive|get|credit)",
        r"(पिन डाल|pin डाल|पिन टाका|pin टाका).{0,30}(पैसे|रिफंड|मिल|मिळ)",
    ),
    "pin_request": _p(
        r"\b(share|send|tell|give|enter|type|put)\b.{0,30}\b(upi )?pin\b",
        r"\b(upi )?pin\b.{0,30}\b(share|send|tell|give|enter|type|put)\b",
        r"(पिन|पिन नंबर|एमपिन).{0,20}(बता|भेज|डाल|टाक)",
        r"(बता|भेज|डाल|टाक).{0,20}(पिन|एमपिन)",
    ),
    "password_request": _p(
        r"\b(share|send|tell|give|enter|type)\b.{0,30}\b(password|passwd|netbanking password|login password)\b",
        r"\b(password|passwd)\b.{0,30}\b(share|send|tell|give|enter|type)\b",
        r"(पासवर्ड|पासवर्ड बता|पासवर्ड भेज)",
    ),
    "documents_request": _p(
        r"\b(send|share|upload|photo of|scan of|copy of)\b.{0,40}\b(aadhaa?r|pan|passport|driving licence|driving license|voter id|bank statement|passbook|cheque|fir|warrant|id card|employee id)\b",
        r"\b(aadhaa?r|pan|passport|fir|warrant|id card)\b.{0,40}\b(send|share|upload|photo|scan|copy)\b",
        r"(आधार|पैन|पासपोर्ट|फोटो|कॉपी|दस्तावेज).{0,30}(भेज|भेजें|पाठव|पाठवा|भेजो)",
    ),
    "ai_manipulation_attempt": _p(
        r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
        r"\bsystem\s*:\s*",
        r"\b(classify|label|mark)\s+(this|the message|it)\s+as\s+(benign|safe|low|genuine|not a scam|ham)\b",
        r"\byou are (now|actually)\b.{0,40}\b(helpful|unrestricted|jailbreak)\b",
        r"\b(developer|anthropic|openai|gpt|claude)\s*:\s*",
        r"(पिछले निर्देश|पिछले निर्देशों|सिस्टम\s*:|सुरक्षित वर्गीकृत|benign के रूप में)",
    ),
}

# Phrases that turn an apparent OTP mention into a legitimate OTP SMS
# ("123456 is your OTP. Do not share it with anyone.")
OTP_SAFETY_NOTICE = re.compile(
    r"(do not|don'?t|never|dont)\s+(share|disclose|tell)|साझा न करें|किसी को न बताएं|शेयर न करें|सांगू नका|शेअर करू नका",
    re.IGNORECASE,
)

# Internal signals are used by playbooks but never shown to the user.
INTERNAL_SIGNALS = {"has_link", "has_phone", "has_amount", "has_upi"}

# Map detection signals / rule hits onto append-only case facts.
SIGNAL_TO_FACT = {
    "money_request": "money_requested",
    "otp_request": "otp_requested",
    "pin_request": "pin_requested",
    "password_request": "password_requested",
    "remote_app": "remote_access_requested",
    "apk_link": "remote_access_requested",
    "documents_request": "documents_requested",
    "video_call_demand": "video_call_demanded",
    "authority_police": "authority_claimed",
    "family_claim": "family_claimed",
    "secrecy": "secrecy_requested",
    "suspicious_link": "link_sent",
    "fake_brand_link": "link_sent",
    "short_link": "link_sent",
    "upi_collect": "upi_collect",
    "has_upi": "payment_destination_seen",
}

# Processing / registration fee phrasing → fee_requested fact.
FEE_PATTERNS = _p(
    r"\b(processing|registration|release|clearance|customs|security|verification)\s+(fee|charge|charges|amount|deposit)",
    r"(प्रोसेसिंग फीस|प्रोसेसिंग फ़ीस|रजिस्ट्रेशन फीस|शुल्क जमा)",
)

# Elder-role stage hints (only apply when role == "elder").
COMPLIANCE_PATTERNS = _p(
    r"\b(i (have |already )?(installed|downloaded|shared|entered|typed|gave|sent them|am on|joined))\b",
    r"\b(he|she|they) (is|are) on (the )?(phone|call|video)\b",
    r"\b(anydesk|teamviewer).{0,20}\b(installed|open|running|code)\b",
    r"(मैंने|मैने).{0,30}(इंस्टॉल|इंस्टाल|डाल दिया|भेज दिया|दे दिया|शेयर|खोल दिया)",
    r"(मी|मीने).{0,30}(इंस्टॉल|टाकले|पाठवले|दिले|शेअर)",
    r"(वीडियो कॉल पर हूँ|व्हिडिओ कॉलवर आहे|on the (video )?call)",
)

LOSS_PATTERNS = _p(
    r"\b(i (have |already )?(sent|transferred|paid|gave them|shared my (otp|pin|password|code)))\b",
    r"\b(money (has )?(gone|left|been (sent|transferred))|paid (them|him|her))\b",
    r"(मैंने|मैने).{0,40}(भेज दिए|भेज दिया|ट्रांसफर|पेमेंट|पैसे भेज|OTP बता|पिन बता)",
    r"(मी|मीने).{0,40}(पाठवले|ट्रान्सफर|पैसे दिले|OTP सांगितला|पिन सांगितला)",
    r"(₹|rs\.?|rupees|पैसे|रुपये).{0,20}(sent|भेज|पाठव)",
)


def detect_signals(text: str) -> set:
    found = set()
    if not text:
        return found
    for signal, patterns in SIGNAL_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            found.add(signal)
    if "otp_request" in found and OTP_SAFETY_NOTICE.search(text):
        found.discard("otp_request")
    # Legitimate OTP / bank alert SMS: mention of a bank + "do not share" and no ask → drop bank_impersonation.
    if (
        "bank_impersonation" in found
        and OTP_SAFETY_NOTICE.search(text)
        and re.search(r"\b(otp|o\.t\.p|one[- ]time password|verification code)\b", text, re.I)
        and not (found & {"money_request", "remote_app", "upi_collect", "apk_link", "suspicious_link", "fake_brand_link"})
    ):
        found.discard("bank_impersonation")
    return found


def detect_stage(text: str, role: str = "other") -> str:
    """
    Furthest stage this item shows.
    compliance/loss only when the older person's own words (role=elder) show it,
    or when the text clearly narrates their action in first person.
    """
    if not text:
        return "contact"
    role = (role or "other").lower()
    if role == "elder":
        if any(p.search(text) for p in LOSS_PATTERNS):
            return "loss"
        if any(p.search(text) for p in COMPLIANCE_PATTERNS):
            return "compliance"
    # First-person loss/compliance can appear when pasted as a self-report.
    if any(p.search(text) for p in LOSS_PATTERNS):
        return "loss"
    if role == "elder" or re.search(r"\bI (installed|sent|paid|shared)\b", text, re.I):
        if any(p.search(text) for p in COMPLIANCE_PATTERNS):
            return "compliance"

    signals = detect_signals(text)
    ask_signals = {
        "otp_request", "money_request", "upi_collect", "remote_app", "apk_link",
        "pin_request", "password_request", "documents_request", "video_call_demand",
    }
    if signals & ask_signals or any(p.search(text) for p in FEE_PATTERNS):
        return "ask"
    hook_signals = {
        "authority_police", "arrest_threat", "parcel", "prize", "investment_returns",
        "job_task", "emotional_bond", "hardship_story", "account_threat", "utility_cut",
        "family_claim", "new_number", "bank_impersonation", "refund",
    }
    if signals & hook_signals:
        return "hook"
    return "contact"


def signals_to_facts(signals: set, text: str = "") -> list[tuple[str, str]]:
    """Return [(fact_name, quote_snippet), ...] for newly suggested facts."""
    out = []
    for sig, fact in SIGNAL_TO_FACT.items():
        if sig in signals:
            out.append((fact, _quote_for(text, sig)))
    if text and any(p.search(text) for p in FEE_PATTERNS):
        out.append(("fee_requested", _quote_for(text, "fee")))
    if "upi_collect" in signals:
        out.append(("upi_collect", _quote_for(text, "upi_collect")))
    return out


def _quote_for(text: str, _hint: str, limit: int = 120) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text[:limit]


def _any(s, *names):
    return bool(s.intersection(names))


# Ordered by priority: the first matching playbook names the category.
PLAYBOOKS = [
    ("digital_arrest", "high",
     lambda s: "authority_police" in s and _any(s, "arrest_threat", "video_call_demand", "parcel", "money_request")),
    ("remote_access", "high",
     lambda s: _any(s, "remote_app", "apk_link")),
    ("upi_collect", "high",
     lambda s: "upi_collect" in s),
    ("otp_theft", "high",
     lambda s: "otp_request" in s),
    ("family_impersonation", "high",
     lambda s: ("new_number" in s and _any(s, "money_request", "urgency", "hardship_story", "has_upi"))
     or ("family_claim" in s and "money_request" in s and _any(s, "urgency", "secrecy", "hardship_story"))),
    ("bank_kyc", "high",
     lambda s: _any(s, "account_threat", "fake_brand_link")
     and _any(s, "bank_impersonation", "fake_brand_link")
     and _any(s, "fake_brand_link", "suspicious_link", "short_link", "urgency", "has_phone")),
    ("utility_cut", "high",
     lambda s: "utility_cut" in s and _any(s, "urgency", "suspicious_link", "short_link", "has_phone", "money_request")),
    ("romance", "high",
     lambda s: "emotional_bond" in s and _any(s, "money_request", "hardship_story")),
    ("investment", "high",
     lambda s: "investment_returns" in s and _any(s, "money_request", "suspicious_link", "short_link", "urgency", "has_amount")),
    ("prize", "high",
     lambda s: "prize" in s and _any(s, "money_request", "suspicious_link", "short_link", "urgency")),
    ("job_task", "high",
     lambda s: "job_task" in s and _any(s, "money_request", "has_amount", "suspicious_link", "short_link")),
    ("fake_link", "high",
     lambda s: "fake_brand_link" in s),
    ("known_reported", "high",
     lambda s: "known_reported" in s),
    ("money_pressure", "high",
     lambda s: "money_request" in s and "secrecy" in s),
    ("refund", "medium",
     lambda s: "refund" in s and _any(s, "suspicious_link", "short_link", "urgency", "has_link")),
]

# Any of these alone is enough to say "be careful".
MEDIUM_SIGNALS = {
    "investment_returns", "prize", "job_task", "account_threat", "utility_cut",
    "authority_police", "arrest_threat", "emotional_bond", "new_number",
    "suspicious_link", "short_link", "secrecy", "video_call_demand",
}


def apply_playbooks(signals: set):
    """Return (risk, category) from signals. Risk is never 'safe' — lowest is 'low'."""
    for category, risk, test in PLAYBOOKS:
        if test(signals):
            return risk, category
    if signals & MEDIUM_SIGNALS or {"money_request", "urgency"} <= signals:
        return "medium", "generic"
    return "low", "none"
