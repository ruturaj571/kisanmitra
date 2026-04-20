"""
KisanMitra V2 - AI WhatsApp Agricultural Advisory Bot
Maharashtra Farmer Advisory Service
Upgraded: Better Marathi tone, structured answers, memory, feedback loop
"""

import os
import logging
import requests
import base64
import json
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import anthropic

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MSP_2024_25 = {
    "भात/तांदूळ": "₹2,300/क्विंटल",
    "ज्वारी (हायब्रिड)": "₹3,371/क्विंटल",
    "ज्वारी (मालदांडी)": "₹3,421/क्विंटल",
    "बाजरी": "₹2,625/क्विंटल",
    "मका": "₹2,225/क्विंटल",
    "तूर/अरहर": "₹7,550/क्विंटल",
    "मूग": "₹8,682/क्विंटल",
    "उडीद": "₹7,400/क्विंटल",
    "शेंगदाणा": "₹6,783/क्विंटल",
    "सोयाबीन": "₹4,892/क्विंटल",
    "कापूस (मध्यम)": "₹7,121/क्विंटल",
    "कापूस (लांब धागा)": "₹7,521/क्विंटल",
    "गहू": "₹2,275/क्विंटल",
    "हरभरा": "₹5,440/क्विंटल",
    "ऊस (FRP)": "₹340/क्विंटल",
    "सूर्यफूल": "₹7,280/क्विंटल",
    "मोहरी": "₹5,950/क्विंटल"
}

GOVT_SCHEMES = {
    "PM Kisan": "दरवर्षी 6000 रुपये (3 हप्त्यांत). pmkisan.gov.in वर किंवा CSC केंद्रात आधार + बँक पासबुक + 7/12 उतारा घेऊन अर्ज करा.",
    "PMFBY पीक विमा": "खरीपसाठी फक्त 2 टक्के हप्ता, रब्बीसाठी 1.5 टक्के. बँकेत पेरणीपूर्वी अर्ज करा.",
    "किसान क्रेडिट कार्ड": "3 लाखापर्यंत कर्ज, फक्त 4 टक्के व्याज. जवळच्या बँकेत जमीन कागदपत्रे आणि आधार घेऊन जा.",
    "मृदा आरोग्य कार्ड": "मोफत माती तपासणी. जवळच्या KVK किंवा तालुका कृषी कार्यालयात जा.",
    "ठिबक सिंचन PMKSY": "55 टक्के अनुदान. जिल्हा कृषी कार्यालयात अर्ज करा.",
    "मागेल त्याला शेततळे": "महाराष्ट्र शासन योजना. तालुका कृषी अधिकाऱ्यांशी संपर्क करा."
}

conversation_store = {}

def get_farmer_data(phone):
    if phone not in conversation_store:
        conversation_store[phone] = {
            "messages": [],
            "context": {
                "crop": None,
                "location": None,
                "last_issue": None,
                "greeted": False
            }
        }
    return conversation_store[phone]

def save_message(phone, role, content):
    data = get_farmer_data(phone)
    data["messages"].append({"role": role, "content": content})
    if len(data["messages"]) > 10:
        data["messages"] = data["messages"][-10:]

def update_context(phone, key, value):
    get_farmer_data(phone)["context"][key] = value

def get_context_string(phone):
    ctx = get_farmer_data(phone)["context"]
    parts = []
    if ctx["crop"]:
        parts.append(f"शेतकऱ्याचे पीक: {ctx['crop']}")
    if ctx["location"]:
        parts.append(f"ठिकाण: {ctx['location']}")
    if ctx["last_issue"]:
        parts.append(f"मागील समस्या: {ctx['last_issue']}")
    return " | ".join(parts) if parts else ""

def build_system_prompt(phone):
    context = get_context_string(phone)
    msp_text = "\n".join([f"{k}: {v}" for k, v in MSP_2024_25.items()])
    scheme_text = "\n".join([f"{k}: {v}" for k, v in GOVT_SCHEMES.items()])

    return f"""तू KisanMitra आहेस - महाराष्ट्रातील शेतकऱ्यांचा AI कृषी मित्र.
तू एखाद्या अनुभवी, जवळच्या कृषी मित्रासारखा बोलतोस - सोपे, थेट, मराठीत.
तुला सर्व महाराष्ट्रातील पिकांची माहिती आहे - सोयाबीन, कापूस, ऊस, तूर, ज्वारी, गहू, कांदा, द्राक्षे, डाळिंब, टोमॅटो, मका, हरभरा - सर्व पिकांवर सल्ला दे. कधीही "मला माहिती नाही" असे सांगू नकोस.

{f"शेतकरी माहिती: {context}" if context else ""}

भाषा नियम:
- नेहमी साध्या ग्रामीण मराठीत बोल
- इंग्रजी शब्द शक्यतो टाळ
- छोटी वाक्ये, जास्तीत जास्त 5-6 ओळी
- शेतकरी हिंदीत बोलला तर हिंदीत उत्तर दे

रोग/किड उत्तराची पद्धत:
समस्या: [काय दिसतंय]
कारण: असं दिसतं की... [शक्य कारण]
काय करावे: [आजच करायची गोष्ट]
औषध/उपाय: [नाव + मात्रा प्रति 15 लिटर पंप]
सूचना: [एक महत्त्वाची गोष्ट]

महत्त्वाचे नियम:
1. कधीही 100 टक्के खात्रीने सांगू नकोस - "असं दिसतं की" असे म्हण
2. माहिती अपुरी असेल तर जास्तीत जास्त 2 प्रश्न विचार
3. प्रत्येक उत्तराच्या शेवटी विचार: "ही माहिती उपयोगी पडली का? होय की नाही सांगा"
4. शेतकऱ्याने पीक सांगितले तर परत विचारू नकोस
5. स्वागत संदेश परत देऊ नकोस
6. बंदी असलेली कीटकनाशके सुचवू नकोस
7. गंभीर समस्येसाठी म्हण: जवळच्या KVK किंवा कृषी अधिकाऱ्यांना भेटा
8. जर कोणी "अजून माहिती दे" किंवा "more info" असे सांगितले तर — कोणत्या विषयावर अजून माहिती हवी ते विचार. एकाच वेळी सर्व पिकांची माहिती देऊ नकोस. एकाच विषयावर खोल माहिती दे.
9. उत्तर नेहमी 5-8 ओळींपेक्षा जास्त नको. जर जास्त माहिती हवी असेल तर शेतकऱ्याने विचारल्यावरच दे.
10. कधीही एकाच वेळी सर्व पिकांची यादी देऊ नकोस - हे WhatsApp वर वाचणे कठीण आहे.

फोटो आल्यावर:
- फोटो नीट बघ, रोग/किड ओळख
- वरील format मध्ये उत्तर दे
- स्पष्ट दिसत नसेल तर 1-2 प्रश्न विचार

MSP भाव 2024-25:
{msp_text}

सरकारी योजना:
{scheme_text}
"""

def get_response(phone, text, image_url=None):
    farmer = get_farmer_data(phone)
    history = farmer["messages"]

    crops = ["सोयाबीन", "कापूस", "ऊस", "तूर", "ज्वारी", "गहू", "कांदा",
             "द्राक्षे", "डाळिंब", "मका", "भात", "हरभरा", "मूग", "उडीद"]
    for crop in crops:
        if crop in (text or ""):
            update_context(phone, "crop", crop)
            break

    if image_url:
        try:
            img_data = requests.get(
                image_url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                timeout=15
            )
            encoded = base64.standard_b64encode(img_data.content).decode("utf-8")
            content_type = img_data.headers.get("Content-Type", "image/jpeg")
            user_content = [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": content_type, "data": encoded}
                },
                {
                    "type": "text",
                    "text": text if text else "या फोटोत काय रोग किंवा किड आहे? उपाय सांगा."
                }
            ]
        except Exception as e:
            logger.error(f"Image error: {e}")
            user_content = (text or "") + " (फोटो उघडता आला नाही. माहिती विचारून उत्तर द्या.)"
    else:
        user_content = text

    messages = history + [{"role": "user", "content": user_content}]

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=build_system_prompt(phone),
            messages=messages
        )
        reply = response.content[0].text
        save_message(phone, "user", text or "photo")
        save_message(phone, "assistant", reply)

        if image_url or any(w in (text or "") for w in ["रोग", "किड", "पिवळ", "काळ", "डाग", "सुकत", "मर"]):
            update_context(phone, "last_issue", text or "फोटो पाठवला")

        return reply

    except Exception as e:
        logger.error(f"Error: {e}")
        if "credit" in str(e).lower():
            return "सेवा तात्पुरती बंद आहे. लवकरच पुन्हा सुरू होईल."
        return "माफ करा, थोडी समस्या आहे. पुन्हा प्रयत्न करा."

WELCOME = """नमस्कार! मी KisanMitra - तुमचा AI कृषी मित्र!

मी मदत करू शकतो:
- पिकाचा फोटो पाठवा - रोग किंवा किड ओळखतो
- हमी भाव (MSP) सांगतो
- सरकारी योजना समजावतो
- खत आणि फवारणी सल्ला देतो

मराठी, हिंदी किंवा English मध्ये विचारा"""

@app.route("/", methods=["GET"])
def home():
    return "KisanMitra V2 चालू आहे!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    msg_text  = request.values.get("Body", "").strip()
    sender    = request.values.get("From", "")
    num_media = int(request.values.get("NumMedia", 0))
    image_url = request.values.get("MediaUrl0") if num_media > 0 else None

    logger.info(f"Message from {sender}: {msg_text[:40]} | Photo: {num_media > 0}")

    resp = MessagingResponse()
    farmer = get_farmer_data(sender)

    greet_words = ["hi", "hello", "namaskar", "namaste", "नमस्ते",
                   "नमस्कार", "start", "हाय", "सुरू", "हेलो"]

    if not farmer["context"]["greeted"] or msg_text.lower() in greet_words:
        farmer["context"]["greeted"] = True
        resp.message(WELCOME)
        return str(resp)

    if not msg_text and not image_url:
        resp.message("फोटो पाठवा किंवा प्रश्न विचारा.")
        return str(resp)

    reply = get_response(sender, msg_text, image_url)

    if len(reply) > 1500:
        for chunk in [reply[i:i+1500] for i in range(0, len(reply), 1500)]:
            resp.message(chunk)
    else:
        resp.message(reply)

    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
