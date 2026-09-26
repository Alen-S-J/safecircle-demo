"""
User-facing wording. Replies are assembled from these reviewed templates rather
than written free-form by an LLM, so tone stays consistent and advice is safe.
Have native speakers review the Hindi and Marathi with older users before launch.
"""

LANGS = ("en", "hi", "mr")

HEADLINES = {
    "critical": {
        "en": "Stop now. This is a serious scam — do not send money or share any code.",
        "hi": "अभी रुक जाएँ। यह गंभीर धोखाधड़ी है — पैसे न भेजें और कोई कोड न बताएं।",
        "mr": "आत्ता थांबा. ही गंभीर फसवणूक आहे — पैसे पाठवू नका आणि कोणताही कोड सांगू नका.",
    },
    "high": {
        "en": "Don't act on this. It looks like a scam.",
        "hi": "इस पर कुछ न करें। यह धोखाधड़ी लगती है।",
        "mr": "यावर काहीही करू नका. ही फसवणूक वाटते.",
    },
    "medium": {
        "en": "Be careful. Check before you reply.",
        "hi": "सावधान रहें। जवाब देने से पहले जाँच लें।",
        "mr": "सावध राहा. उत्तर देण्यापूर्वी खात्री करा.",
    },
    "low": {
        "en": "No warning signs found.",
        "hi": "कोई चेतावनी संकेत नहीं मिला।",
        "mr": "धोक्याची कोणतीही चिन्हे आढळली नाहीत.",
    },
    "none": {
        "en": "No warning signs found.",
        "hi": "कोई चेतावनी संकेत नहीं मिला।",
        "mr": "धोक्याची कोणतीही चिन्हे आढळली नाहीत.",
    },
}

FOOTER = {
    "en": "Remember: never share an OTP, and check any money request by calling a number you already know.",
    "hi": "याद रखें: OTP कभी किसी को न बताएं, और पैसे माँगे जाएँ तो पहले से पता नंबर पर फ़ोन करके पूछें।",
    "mr": "लक्षात ठेवा: OTP कधीही कोणालाही सांगू नका, आणि पैसे मागितले तर आधीपासून माहीत असलेल्या नंबरवर फोन करून खात्री करा.",
}

SIGNAL_TEXT = {
    "otp_request": ("Asks you to share an OTP or code", "OTP या कोड बताने को कह रहा है", "OTP किंवा कोड सांगायला सांगत आहे"),
    "money_request": ("Asks for money or a fee", "पैसे या फ़ीस माँग रहा है", "पैसे किंवा फी मागत आहे"),
    "urgency": ("Pushes you to act fast", "जल्दी करने का दबाव डाल रहा है", "घाई करायला भाग पाडत आहे"),
    "new_number": ("Says it's someone you know, on a new number", "जान-पहचान वाला होने का दावा, नए नंबर से", "ओळखीचे असल्याचा दावा, नवीन नंबरवरून"),
    "family_claim": ("Claims to be family", "परिवार का सदस्य होने का दावा", "कुटुंबातील व्यक्ती असल्याचा दावा"),
    "secrecy": ("Asks you to keep it secret", "किसी को न बताने को कह रहा है", "कोणालाही न सांगायला सांगत आहे"),
    "authority_police": ("Claims to be police or a government agency", "पुलिस या सरकारी एजेंसी होने का दावा", "पोलीस किंवा सरकारी यंत्रणा असल्याचा दावा"),
    "arrest_threat": ("Threatens arrest or legal action", "गिरफ्तारी या कानूनी कार्रवाई की धमकी", "अटक किंवा कायदेशीर कारवाईची धमकी"),
    "video_call_demand": ("Wants you to stay on a video call", "वीडियो कॉल पर रहने को कह रहा है", "व्हिडिओ कॉलवर राहायला सांगत आहे"),
    "parcel": ("Mentions a parcel or courier problem", "पार्सल या कूरियर की समस्या बता रहा है", "पार्सल किंवा कुरिअरची अडचण सांगत आहे"),
    "bank_impersonation": ("Claims to be from a bank", "बैंक से होने का दावा", "बँकेकडून असल्याचा दावा"),
    "account_threat": ("Threatens to block your account or card", "खाता या कार्ड बंद करने की धमकी", "खाते किंवा कार्ड बंद करण्याची धमकी"),
    "utility_cut": ("Threatens to cut your electricity", "बिजली काटने की धमकी", "वीज बंद करण्याची धमकी"),
    "remote_app": ("Asks you to install an app or share your screen", "कोई ऐप डालने या स्क्रीन शेयर करने को कह रहा है", "ॲप टाकायला किंवा स्क्रीन शेअर करायला सांगत आहे"),
    "prize": ("Says you won a prize or lottery", "इनाम या लॉटरी जीतने की बात", "बक्षीस किंवा लॉटरी लागल्याचे सांगत आहे"),
    "investment_returns": ("Promises big or guaranteed profits", "बड़े या पक्के मुनाफ़े का वादा", "मोठ्या किंवा खात्रीच्या नफ्याचे आश्वासन"),
    "job_task": ("Offers easy money for simple online tasks", "आसान ऑनलाइन काम के बदले पैसे का लालच", "सोप्या ऑनलाइन कामासाठी पैशाचे आमिष"),
    "refund": ("Offers a refund or cashback", "रिफ़ंड या कैशबैक का लालच", "परतावा किंवा कॅशबॅकचे आमिष"),
    "emotional_bond": ("Uses loving words to win your trust", "भरोसा जीतने के लिए भावुक बातें", "विश्वास मिळवण्यासाठी भावनिक बोलणे"),
    "hardship_story": ("Tells an emergency or sad story", "इमरजेंसी या दुख की कहानी", "संकटाची किंवा दुःखाची कहाणी"),
    "upi_collect": ("Asks you to enter your UPI PIN or approve a request", "UPI PIN डालने या रिक्वेस्ट मंज़ूर करने को कह रहा है", "UPI PIN टाकायला किंवा विनंती मंजूर करायला सांगत आहे"),
    "suspicious_link": ("Contains a suspicious link", "इसमें संदिग्ध लिंक है", "यात संशयास्पद लिंक आहे"),
    "fake_brand_link": ("The link pretends to be a bank or government site", "लिंक किसी बैंक या सरकारी साइट की नकल है", "लिंक बँक किंवा सरकारी साइटची नक्कल आहे"),
    "short_link": ("Uses a short link that hides where it goes", "छोटा लिंक असली पता छुपाता है", "छोटी लिंक खरा पत्ता लपवते"),
    "apk_link": ("The link downloads an app file (APK)", "लिंक से ऐप फ़ाइल (APK) डाउनलोड होगी", "लिंकमधून ॲप फाइल (APK) डाउनलोड होईल"),
    "known_reported": ("This number or link was reported by other users", "इस नंबर या लिंक की शिकायत पहले भी हुई है", "या नंबर किंवा लिंकची आधीही तक्रार झाली आहे"),
    "pin_request": ("Asks for your PIN", "आपका PIN माँग रहा है", "तुमचा PIN मागत आहे"),
    "password_request": ("Asks for your password", "पासवर्ड माँग रहा है", "पासवर्ड मागत आहे"),
    "documents_request": ("Asks for identity documents", "पहचान दस्तावेज़ माँग रहा है", "ओळखपत्र मागत आहे"),
    "ai_manipulation_attempt": ("Tries to instruct or override the checker", "जाँच को निर्देश देने की कोशिश", "तपासणीला निर्देश देण्याचा प्रयत्न"),
}

# Signals shown first when there are more than we can list.
SIGNAL_PRIORITY = [
    "known_reported", "otp_request", "upi_collect", "remote_app", "apk_link", "fake_brand_link",
    "arrest_threat", "authority_police", "video_call_demand", "new_number", "money_request",
    "pin_request", "password_request", "documents_request", "ai_manipulation_attempt",
    "secrecy", "account_threat", "utility_cut", "investment_returns", "prize", "job_task",
    "emotional_bond", "hardship_story", "refund", "urgency", "suspicious_link", "short_link",
    "family_claim", "parcel", "bank_impersonation",
]

ACTIONS = {
    "digital_arrest": {
        "en": "Hang up. Real police never arrest or question anyone over a video call, and never ask for money. If you feel scared, call 1930.",
        "hi": "कॉल काट दें। असली पुलिस कभी वीडियो कॉल पर गिरफ्तारी या पूछताछ नहीं करती और पैसे नहीं माँगती। डर लगे तो 1930 पर कॉल करें।",
        "mr": "कॉल बंद करा. खरे पोलीस कधीही व्हिडिओ कॉलवर अटक किंवा चौकशी करत नाहीत आणि पैसे मागत नाहीत. भीती वाटल्यास 1930 वर कॉल करा.",
    },
    "remote_access": {
        "en": "Don't install anything and don't share your screen. Whoever sees your screen can see your bank details.",
        "hi": "कुछ भी इंस्टॉल न करें और अपनी स्क्रीन शेयर न करें। जो आपकी स्क्रीन देखेगा, वह आपकी बैंक जानकारी भी देख लेगा।",
        "mr": "काहीही इन्स्टॉल करू नका आणि स्क्रीन शेअर करू नका. तुमची स्क्रीन पाहणाऱ्याला तुमची बँक माहितीही दिसते.",
    },
    "upi_collect": {
        "en": "You never need a UPI PIN to receive money. Don't enter your PIN.",
        "hi": "पैसे पाने के लिए कभी UPI PIN की ज़रूरत नहीं होती। अपना PIN न डालें।",
        "mr": "पैसे मिळवण्यासाठी कधीही UPI PIN लागत नाही. तुमचा PIN टाकू नका.",
    },
    "otp_theft": {
        "en": "Never share an OTP. No bank, company or officer will ever ask you for it.",
        "hi": "OTP कभी किसी को न बताएं। कोई बैंक, कंपनी या अधिकारी इसे कभी नहीं माँगता।",
        "mr": "OTP कधीही कोणालाही सांगू नका. कोणतीही बँक, कंपनी किंवा अधिकारी तो कधीच मागत नाही.",
    },
    "family_impersonation": {
        "en": "Don't send money. Call your family member on the number you already have for them.",
        "hi": "पैसे न भेजें। अपने परिवार वाले को उनके पुराने, जाने-पहचाने नंबर पर फ़ोन करके पूछें।",
        "mr": "पैसे पाठवू नका. कुटुंबातील त्या व्यक्तीला त्यांच्या जुन्या, ओळखीच्या नंबरवर फोन करून विचारा.",
    },
    "bank_kyc": {
        "en": "Don't open the link. Call the number printed on the back of your bank card.",
        "hi": "लिंक न खोलें। अपने बैंक कार्ड के पीछे छपे नंबर पर फ़ोन करें।",
        "mr": "लिंक उघडू नका. तुमच्या बँक कार्डच्या मागे छापलेल्या नंबरवर फोन करा.",
    },
    "bank_kyc_call": {
        "en": "Don't call that number. Call only the number printed on the back of your bank card.",
        "hi": "उस नंबर पर फ़ोन न करें। सिर्फ़ अपने बैंक कार्ड के पीछे छपे नंबर पर फ़ोन करें।",
        "mr": "त्या नंबरवर फोन करू नका. फक्त तुमच्या बँक कार्डच्या मागे छापलेल्या नंबरवर फोन करा.",
    },
    "utility_cut": {
        "en": "Don't call that number or pay through it. Check your bill in the official app or at the electricity office.",
        "hi": "उस नंबर पर फ़ोन या भुगतान न करें। अपना बिल आधिकारिक ऐप या बिजली दफ़्तर से जाँचें।",
        "mr": "त्या नंबरवर फोन किंवा पैसे भरू नका. तुमचे बिल अधिकृत ॲपवर किंवा वीज कार्यालयात तपासा.",
    },
    "romance": {
        "en": "Don't send money to someone you have only met online, however kind they seem.",
        "hi": "जिससे सिर्फ़ ऑनलाइन मिले हों, उसे पैसे न भेजें, चाहे वह कितना भी अच्छा लगे।",
        "mr": "ज्यांना फक्त ऑनलाइन भेटलात त्यांना पैसे पाठवू नका, ते कितीही चांगले वाटले तरी.",
    },
    "investment": {
        "en": "Don't send money. Nobody can guarantee high profits; that promise is the trick.",
        "hi": "पैसे न भेजें। कोई भी बड़े मुनाफ़े की गारंटी नहीं दे सकता; यही वादा धोखा है।",
        "mr": "पैसे पाठवू नका. मोठ्या नफ्याची खात्री कोणीच देऊ शकत नाही; हेच आश्वासन फसवणूक आहे.",
    },
    "prize": {
        "en": "Don't pay any fee. You can't win a lottery you never entered.",
        "hi": "कोई फ़ीस न भरें। जिस लॉटरी में आपने भाग ही नहीं लिया, उसे आप जीत नहीं सकते।",
        "mr": "कोणतीही फी भरू नका. ज्या लॉटरीत तुम्ही भागच घेतला नाही, ती तुम्हाला लागू शकत नाही.",
    },
    "job_task": {
        "en": "Don't pay anything. A real job never asks you to pay before you earn.",
        "hi": "कुछ भी न भरें। असली नौकरी कमाने से पहले पैसे नहीं माँगती।",
        "mr": "काहीही भरू नका. खरी नोकरी कमाईच्या आधी पैसे मागत नाही.",
    },
    "refund": {
        "en": "Don't click. Check refunds only in the official app or website you already use.",
        "hi": "क्लिक न करें। रिफ़ंड सिर्फ़ उसी आधिकारिक ऐप या वेबसाइट पर जाँचें जो आप पहले से इस्तेमाल करते हैं।",
        "mr": "क्लिक करू नका. परतावा फक्त तुम्ही आधीपासून वापरत असलेल्या अधिकृत ॲपवर किंवा वेबसाइटवर तपासा.",
    },
    "generic_high": {
        "en": "Don't send money, open links or share any code. Ask someone you trust to look at this.",
        "hi": "पैसे न भेजें, लिंक न खोलें और कोई कोड न बताएं। किसी भरोसेमंद व्यक्ति को यह दिखाएं।",
        "mr": "पैसे पाठवू नका, लिंक उघडू नका आणि कोणताही कोड सांगू नका. विश्वासू व्यक्तीला हे दाखवा.",
    },
    "generic_medium": {
        "en": "Don't reply or click yet. Check with someone you trust first.",
        "hi": "अभी जवाब न दें और क्लिक न करें। पहले किसी भरोसेमंद व्यक्ति से पूछ लें।",
        "mr": "आत्ता उत्तर देऊ नका किंवा क्लिक करू नका. आधी विश्वासू व्यक्तीला विचारा.",
    },
}

ADVICE_EXTRA = {
    "critical": {
        "en": ["Stop. Do not send money, share codes, or stay on the call.",
               "If you already paid or shared details, call 1930 right now, then call your bank.",
               "Ask your family to call you."],
        "hi": ["रुक जाएँ। पैसे न भेजें, कोड न बताएं, कॉल पर न रहें।",
               "अगर पैसे भेज दिए हैं या जानकारी दे दी है, तो तुरंत 1930 पर कॉल करें, फिर अपने बैंक को।",
               "अपने परिवार से कहें कि वे आपको फ़ोन करें।"],
        "mr": ["थांबा. पैसे पाठवू नका, कोड सांगू नका, कॉलवर राहू नका.",
               "पैसे पाठवले असतील किंवा माहिती दिली असेल, तर लगेच 1930 वर कॉल करा, मग तुमच्या बँकेला.",
               "कुटुंबाला सांगा की ते तुम्हाला फोन करावे."],
    },
    "high": {
        "en": ["Don't reply to this message or call back.",
               "If you already paid or shared details, call 1930 right now, then call your bank.",
               "Show this to someone in your family."],
        "hi": ["इस मैसेज का जवाब न दें और वापस फ़ोन न करें।",
               "अगर पैसे भेज दिए हैं या जानकारी दे दी है, तो तुरंत 1930 पर कॉल करें, फिर अपने बैंक को।",
               "यह अपने परिवार में किसी को दिखाएं।"],
        "mr": ["या मेसेजला उत्तर देऊ नका आणि परत फोन करू नका.",
               "पैसे पाठवले असतील किंवा माहिती दिली असेल, तर लगेच 1930 वर कॉल करा, मग तुमच्या बँकेला.",
               "हे कुटुंबातील कोणाला तरी दाखवा."],
    },
    "medium": {
        "en": ["If it claims to be from someone you know, call them on the number you already have.",
               "Never share an OTP or PIN, whatever the message says."],
        "hi": ["अगर यह किसी जान-पहचान वाले के नाम से है, तो उन्हें उनके पुराने नंबर पर फ़ोन करें।",
               "मैसेज में कुछ भी लिखा हो, OTP या PIN कभी न बताएं।"],
        "mr": ["ओळखीच्या व्यक्तीच्या नावाने असेल, तर त्यांना त्यांच्या जुन्या नंबरवर फोन करा.",
               "मेसेजमध्ये काहीही लिहिले असले तरी OTP किंवा PIN कधीही सांगू नका."],
    },
    "low": {
        "en": ["I didn't find warning signs, but I can miss new tricks.",
               "If it asks for money, an OTP or a PIN later, send it to me again."],
        "hi": ["मुझे चेतावनी के संकेत नहीं मिले, लेकिन नई चालें मुझसे छूट सकती हैं।",
               "अगर बाद में पैसे, OTP या PIN माँगा जाए, तो मुझे फिर से भेजें।"],
        "mr": ["मला धोक्याची चिन्हे आढळली नाहीत, पण नवीन युक्त्या माझ्याकडून सुटू शकतात.",
               "नंतर पैसे, OTP किंवा PIN मागितला तर मला पुन्हा पाठवा."],
    },
    "none": {
        "en": ["I didn't find warning signs, but I can miss new tricks.",
               "If it asks for money, an OTP or a PIN later, send it to me again."],
        "hi": ["मुझे चेतावनी के संकेत नहीं मिले, लेकिन नई चालें मुझसे छूट सकती हैं।",
               "अगर बाद में पैसे, OTP या PIN माँगा जाए, तो मुझे फिर से भेजें।"],
        "mr": ["मला धोक्याची चिन्हे आढळली नाहीत, पण नवीन युक्त्या माझ्याकडून सुटू शकतात.",
               "नंतर पैसे, OTP किंवा PIN मागितला तर मला पुन्हा पाठवा."],
    },
}

RECOVERY = {
    "en": [
        "Call 1930 now (national cybercrime helpline).",
        "Then call your bank on the number printed on your card and report the transaction.",
        "Do not pay any more money or share any more codes.",
    ],
    "hi": [
        "अभी 1930 पर कॉल करें (राष्ट्रीय साइबर अपराध हेल्पलाइन)।",
        "फिर अपने बैंक कार्ड के पीछे छपे नंबर पर बैंक को कॉल करें और लेनदेन की रिपोर्ट करें।",
        "और पैसे न भेजें और कोई कोड न बताएं।",
    ],
    "mr": [
        "आत्ता 1930 वर कॉल करा (राष्ट्रीय सायबर गुन्हा हेल्पलाइन).",
        "मग तुमच्या कार्डवर छापलेल्या नंबरवर बँकेला कॉल करा आणि व्यवहाराची तक्रार करा.",
        "आणखी पैसे पाठवू नका आणि कोणताही कोड सांगू नका.",
    ],
}

FAMILY_ALERTED = {
    "en": "I've told {guardian}. They can see this warning too.",
    "hi": "मैंने {guardian} को बता दिया है। वे भी यह चेतावनी देख सकते हैं।",
    "mr": "मी {guardian} यांना कळवले आहे. तेही ही चेतावनी पाहू शकतात.",
}

NUDGE_REWARN = {
    "en": "You're still talking to the same sender after a serious warning. Ask your family before you reply.",
    "hi": "गंभीर चेतावनी के बाद भी आप उसी भेजने वाले से बात कर रहे हैं। जवाब देने से पहले परिवार से पूछें।",
    "mr": "गंभीर चेतावनीनंतरही तुम्ही त्याच पाठवणाऱ्याशी बोलत आहात. उत्तर देण्यापूर्वी कुटुंबाला विचारा.",
}

DONT_REPLY = {
    "en": "Don't reply",
    "hi": "जवाब न दें",
    "mr": "उत्तर देऊ नका",
}

# Pre-written reply drafts per category × language (fallback when Agent 2 fails validation).
TEMPLATE_DRAFTS = {
    "digital_arrest": {
        "en": [
            {"purpose": "verify_official", "text": "I will go to the police station in person and speak there."},
            {"purpose": "end", "text": "I will not discuss this on a call. Please do not contact me again."},
        ],
        "hi": [
            {"purpose": "verify_official", "text": "मैं खुद पुलिस स्टेशन जाकर बात करूँगा।"},
            {"purpose": "end", "text": "मैं इस बारे में फ़ोन पर बात नहीं करूँगा।"},
        ],
        "mr": [
            {"purpose": "verify_official", "text": "मी स्वतः पोलीस स्टेशनला जाऊन बोलेन."},
            {"purpose": "end", "text": "मी याबाबत फोनवर बोलणार नाही."},
        ],
    },
    "family_impersonation": {
        "en": [
            {"purpose": "verify_official", "text": "I will call you on the number I already have saved."},
            {"purpose": "end", "text": "I cannot send money from a new number. I will call you myself."},
        ],
        "hi": [
            {"purpose": "verify_official", "text": "मैं आपके पुराने नंबर पर खुद फ़ोन करके पूछूँगा।"},
            {"purpose": "end", "text": "नए नंबर पर पैसे नहीं भेज सकता। मैं खुद कॉल करूँगा।"},
        ],
        "mr": [
            {"purpose": "verify_official", "text": "मी तुमच्या जुन्या नंबरवर स्वतः फोन करून विचारेन."},
            {"purpose": "end", "text": "नवीन नंबरवर पैसे पाठवू शकत नाही. मी स्वतः कॉल करेन."},
        ],
    },
    "bank_kyc": {
        "en": [
            {"purpose": "verify_official", "text": "I will call my bank on the number printed on my card."},
            {"purpose": "refuse", "text": "I will not open links or share any codes."},
        ],
        "hi": [
            {"purpose": "verify_official", "text": "मैं अपने कार्ड पर छपे नंबर पर बैंक को कॉल करूँगा।"},
            {"purpose": "refuse", "text": "मैं कोई लिंक नहीं खोलूँगा और कोई कोड नहीं बताऊँगा।"},
        ],
        "mr": [
            {"purpose": "verify_official", "text": "मी कार्डवर छापलेल्या नंबरवर बँकेला कॉल करेन."},
            {"purpose": "refuse", "text": "मी लिंक उघडणार नाही आणि कोड सांगणार नाही."},
        ],
    },
    "otp_theft": {
        "en": [
            {"purpose": "refuse", "text": "I will not share any code. I will call my bank myself."},
            {"purpose": "end", "text": "Please stop. I will not discuss this further."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "मैं कोई कोड नहीं बताऊँगा। बैंक को खुद कॉल करूँगा।"},
            {"purpose": "end", "text": "कृपया बंद करें। मैं आगे बात नहीं करूँगा।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "मी कोणताही कोड सांगणार नाही. बँकेला स्वतः कॉल करेन."},
            {"purpose": "end", "text": "कृपया थांबा. मी पुढे बोलणार नाही."},
        ],
    },
    "upi_collect": {
        "en": [
            {"purpose": "refuse", "text": "I will not enter any PIN. I will check in my own bank app."},
            {"purpose": "end", "text": "I am not approving any request. Please do not message again."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "मैं कोई पिन नहीं डालूँगा। अपनी बैंक ऐप में खुद जाँचूँगा।"},
            {"purpose": "end", "text": "मैं कोई रिक्वेस्ट मंज़ूर नहीं करूँगा।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "मी कोणताही पिन टाकणार नाही. स्वतःच्या बँक ॲपमध्ये तपासेन."},
            {"purpose": "end", "text": "मी कोणतीही विनंती मंजूर करणार नाही."},
        ],
    },
    "remote_access": {
        "en": [
            {"purpose": "refuse", "text": "I will not install any app or share my screen."},
            {"purpose": "end", "text": "I will call my bank myself. Please do not contact me."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "मैं कोई ऐप नहीं डालूँगा और स्क्रीन शेयर नहीं करूँगा।"},
            {"purpose": "end", "text": "मैं बैंक को खुद कॉल करूँगा। कृपया संपर्क न करें।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "मी कोणतेही ॲप इन्स्टॉल करणार नाही आणि स्क्रीन शेअर करणार नाही."},
            {"purpose": "end", "text": "मी बँकेला स्वतः कॉल करेन. कृपया संपर्क करू नका."},
        ],
    },
    "investment": {
        "en": [
            {"purpose": "refuse", "text": "I am not interested. Please do not contact me."},
            {"purpose": "end", "text": "I will not send any money for this."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "मुझे दिलचस्पी नहीं है। कृपया संपर्क न करें।"},
            {"purpose": "end", "text": "मैं इसके लिए पैसे नहीं भेजूँगा।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "मला रस नाही. कृपया संपर्क करू नका."},
            {"purpose": "end", "text": "मी यासाठी पैसे पाठवणार नाही."},
        ],
    },
    "romance": {
        "en": [
            {"purpose": "refuse", "text": "I cannot help with money. Please do not ask again."},
            {"purpose": "end", "text": "I will not send money. Goodbye."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "मैं पैसे से मदद नहीं कर सकता। कृपया फिर न पूछें।"},
            {"purpose": "end", "text": "मैं पैसे नहीं भेजूँगा। अलविदा।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "मी पैशाने मदत करू शकत नाही. कृपया पुन्हा विचारू नका."},
            {"purpose": "end", "text": "मी पैसे पाठवणार नाही. नमस्कार."},
        ],
    },
    "prize": {
        "en": [
            {"purpose": "refuse", "text": "I did not enter any lottery. Do not contact me."},
            {"purpose": "end", "text": "I will not pay any fee."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "मैंने कोई लॉटरी नहीं भरी। संपर्क न करें।"},
            {"purpose": "end", "text": "मैं कोई फ़ीस नहीं भरूँगा।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "मी कोणतीही लॉटरी भरलेली नाही. संपर्क करू नका."},
            {"purpose": "end", "text": "मी कोणतीही फी भरणार नाही."},
        ],
    },
    "job_task": {
        "en": [
            {"purpose": "refuse", "text": "I am not interested in paying to start any work."},
            {"purpose": "end", "text": "Please do not message me again."},
        ],
        "hi": [
            {"purpose": "refuse", "text": "काम शुरू करने के लिए पैसे नहीं दूँगा।"},
            {"purpose": "end", "text": "कृपया फिर मैसेज न करें।"},
        ],
        "mr": [
            {"purpose": "refuse", "text": "काम सुरू करण्यासाठी पैसे देणार नाही."},
            {"purpose": "end", "text": "कृपया पुन्हा मेसेज करू नका."},
        ],
    },
    "utility_cut": {
        "en": [
            {"purpose": "verify_official", "text": "I will check my bill in the official app or office."},
            {"purpose": "end", "text": "I will not call unknown numbers or pay through them."},
        ],
        "hi": [
            {"purpose": "verify_official", "text": "मैं बिल आधिकारिक ऐप या दफ़्तर से जाँचूँगा।"},
            {"purpose": "end", "text": "मैं अजनबी नंबर पर कॉल या भुगतान नहीं करूँगा।"},
        ],
        "mr": [
            {"purpose": "verify_official", "text": "मी बिल अधिकृत ॲप किंवा कार्यालयात तपासेन."},
            {"purpose": "end", "text": "मी अनोळखी नंबरवर फोन किंवा पेमेंट करणार नाही."},
        ],
    },
    "generic": {
        "en": [
            {"purpose": "end", "text": "I will not reply further. Please do not contact me."},
            {"purpose": "verify_official", "text": "I will verify this through an official channel I already trust."},
        ],
        "hi": [
            {"purpose": "end", "text": "मैं आगे जवाब नहीं दूँगा। कृपया संपर्क न करें।"},
            {"purpose": "verify_official", "text": "मैं इसे भरोसेमंद आधिकारिक माध्यम से जाँचूँगा।"},
        ],
        "mr": [
            {"purpose": "end", "text": "मी पुढे उत्तर देणार नाही. कृपया संपर्क करू नका."},
            {"purpose": "verify_official", "text": "मी हे विश्वासू अधिकृत मार्गाने तपासेन."},
        ],
    },
}

BUTTONS = {
    "ask_family": {"en": "Ask my family", "hi": "परिवार से पूछें", "mr": "कुटुंबाला विचारा"},
    "advice": {"en": "What should I do?", "hi": "अब क्या करूँ?", "mr": "आता काय करू?"},
    "report": {"en": "Report this", "hi": "शिकायत करें", "mr": "तक्रार करा"},
}

MESSAGES = {
    "asked_family": {
        "en": "I've told {guardian}. They'll call you soon. Until then, don't send money or share any code.",
        "hi": "मैंने {guardian} को बता दिया है। वे जल्द आपको फ़ोन करेंगे। तब तक पैसे न भेजें और कोई कोड न बताएं।",
        "mr": "मी {guardian} यांना कळवले आहे. ते लवकरच तुम्हाला फोन करतील. तोपर्यंत पैसे पाठवू नका आणि कोणताही कोड सांगू नका.",
    },
    "no_guardian": {
        "en": "No family member is linked yet. Add one in settings.",
        "hi": "अभी कोई परिवार सदस्य जुड़ा नहीं है। सेटिंग्स में जोड़ें।",
        "mr": "अजून कुटुंबातील कोणीही जोडलेले नाही. सेटिंग्जमध्ये जोडा.",
    },
    "reported": {
        "en": "Thank you. I'll warn others who get this number or link. To report officially, call 1930 or visit cybercrime.gov.in.",
        "hi": "धन्यवाद। जिन्हें यह नंबर या लिंक मिलेगा, उन्हें मैं सावधान करूँगा। आधिकारिक शिकायत के लिए 1930 पर कॉल करें या cybercrime.gov.in पर जाएँ।",
        "mr": "धन्यवाद. हा नंबर किंवा लिंक मिळणाऱ्यांना मी सावध करेन. अधिकृत तक्रारीसाठी 1930 वर कॉल करा किंवा cybercrime.gov.in वर जा.",
    },
    "needs_ai": {
        "en": "I can read screenshots when AI checking is turned on. For now, please type or paste the message.",
        "hi": "AI जाँच चालू होने पर मैं स्क्रीनशॉट पढ़ सकता हूँ। अभी के लिए, कृपया मैसेज टाइप या पेस्ट करें।",
        "mr": "AI तपासणी चालू असताना मी स्क्रीनशॉट वाचू शकतो. सध्या कृपया मेसेज टाइप किंवा पेस्ट करा.",
    },
    "empty": {
        "en": "Send me the message, link or screenshot you want me to check.",
        "hi": "जिस मैसेज, लिंक या स्क्रीनशॉट की जाँच करनी है, वह मुझे भेजें।",
        "mr": "जो मेसेज, लिंक किंवा स्क्रीनशॉट तपासायचा आहे तो मला पाठवा.",
    },
}

CATEGORY_NAMES = {
    "digital_arrest": "Fake police / digital arrest",
    "remote_access": "Remote-access app",
    "upi_collect": "UPI PIN trick",
    "otp_theft": "OTP theft",
    "family_impersonation": "Family impersonation",
    "bank_kyc": "Fake bank / KYC",
    "utility_cut": "Fake electricity notice",
    "romance": "Romance / emotional scam",
    "investment": "Investment scam",
    "prize": "Lottery / prize scam",
    "job_task": "Task / job scam",
    "refund": "Refund scam",
    "fake_link": "Fake website",
    "known_reported": "Previously reported",
    "money_pressure": "Pressure to pay",
    "generic": "Unusual message",
    "none": "No warning signs",
}


def lang_or_default(lang):
    return lang if lang in LANGS else "en"


def signal_label(signal, lang):
    idx = LANGS.index(lang_or_default(lang))
    return SIGNAL_TEXT[signal][idx] if signal in SIGNAL_TEXT else None


def action_for(category, risk, lang, signals=()):
    lang = lang_or_default(lang)
    if risk == "low":
        return ""
    if category == "bank_kyc" and "has_link" not in signals:
        category = "bank_kyc_call"
    if category in ACTIONS:
        return ACTIONS[category][lang]
    return ACTIONS["generic_high" if risk == "high" else "generic_medium"][lang]


def compose(risk, category, signals, lang, guardian_linked=True, severity=None):
    lang = lang_or_default(lang)
    sev = severity or ({"high": "high", "medium": "medium", "low": "none"}.get(risk, "none"))
    if sev == "critical":
        headline_key = "critical"
    elif sev == "high" or risk == "high":
        headline_key = "high"
    elif sev == "medium" or risk == "medium":
        headline_key = "medium"
    else:
        headline_key = "none"
    ordered = [s for s in SIGNAL_PRIORITY if s in signals]
    reasons = [signal_label(s, lang) for s in ordered][:4] if headline_key not in ("low", "none") else []
    reasons = [r for r in reasons if r]
    headline = HEADLINES[headline_key][lang]
    action_risk = "high" if sev in ("high", "critical") else ("medium" if sev == "medium" else "low")
    action = action_for(category, action_risk, lang, signals)
    if sev == "critical" and not action:
        action = ACTIONS["generic_high"][lang]
    buttons = [
        {"id": "ask_family", "label": BUTTONS["ask_family"][lang]},
        {"id": "advice", "label": BUTTONS["advice"][lang]},
        {"id": "report", "label": BUTTONS["report"][lang]},
    ]
    if headline_key in ("low", "none"):
        buttons = [b for b in buttons if b["id"] != "report"]
    speech = " ".join(x for x in [headline, action or FOOTER[lang]] if x)
    return {
        "headline": headline,
        "reasons": reasons,
        "action": action,
        "footer": FOOTER[lang],
        "buttons": buttons,
        "speech": speech,
        "severity": sev,
    }


def advice(risk, category, lang, signals=(), severity=None):
    lang = lang_or_default(lang)
    sev = severity or ({"high": "high", "medium": "medium", "low": "none"}.get(risk, "none"))
    action_risk = "high" if sev in ("high", "critical") else ("medium" if sev == "medium" else "low")
    first = action_for(category, action_risk, lang, signals)
    extra_key = sev if sev in ADVICE_EXTRA else action_risk
    if extra_key not in ADVICE_EXTRA:
        extra_key = "low"
    steps = ([first] if first else []) + ADVICE_EXTRA[extra_key][lang]
    return steps


def recovery(lang: str) -> list[str]:
    return list(RECOVERY[lang_or_default(lang)])


def family_alerted_message(lang: str, guardian: str) -> str:
    return FAMILY_ALERTED[lang_or_default(lang)].format(guardian=guardian or "your family")
