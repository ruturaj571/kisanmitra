"""
KisanBot - AI WhatsApp Agricultural Advisory Bot
Maharashtra Farmer Advisory Service
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

# ── Maharashtra Crop Knowledge ─────────────────────────────────────────────────
MAHARASHTRA_CROPS = {
    "sugarcane": {
        "marathi": "ऊस",
        "diseases": ["Red Rot (तांबेरा)", "Wilt (मर रोग)", "Smut (काजळी)", "Pokkah Boeng"],
        "pests": ["Pyrilla (पायरिला)", "Top Borer (शेंडा अळी)", "Early Shoot Borer", "Woolly Aphid (लोकरी माव)"],
        "districts": ["Kolhapur", "Solapur", "Sangli", "Satara", "Ahmednagar"]
    },
    "soybean": {
        "marathi": "सोयाबीन",
        "diseases": ["Yellow Mosaic Virus (पिवळा मोझेक)", "Bacterial Pustule", "Charcoal Rot"],
        "pests": ["Stem Fly (खोड माशी)", "Girdle Beetle (खोड किडा)", "Spodoptera (लष्करी अळी)"],
        "districts": ["Latur", "Osmanabad", "Nanded", "Aurangabad", "Buldhana"]
    },
    "cotton": {
        "marathi": "कापूस",
        "diseases": ["Bacterial Blight (पानावरील करपा)", "Fusarium Wilt (मर रोग)", "Alternaria Leaf Spot"],
        "pests": ["Pink Bollworm (गुलाबी बोंड अळी)", "American Bollworm", "Whitefly (पांढरी माशी)", "Thrips"],
        "districts": ["Vidarbha", "Marathwada", "Jalgaon", "Dhule"]
    },
    "wheat": {
        "marathi": "गहू",
        "diseases": ["Yellow Rust (पिवळी गंज)", "Brown Rust (तपकिरी गंज)", "Loose Smut", "Powdery Mildew"],
        "pests": ["Aphid (माव)", "Termite (वाळवी)", "Army Worm"],
        "districts": ["Nashik", "Pune", "Ahmednagar"]
    },
    "onion": {
        "marathi": "कांदा",
        "diseases": ["Purple Blotch (जांभळा डाग)", "Stemphylium Blight", "Basal Rot", "Downy Mildew"],
        "pests": ["Thrips (फुलकिडे)", "Onion Fly", "Maggot"],
        "districts": ["Nashik", "Pune", "Ahmednagar", "Solapur"]
    },
    "jowar": {
        "marathi": "ज्वारी",
        "diseases": ["Grain Mold (दाण्यांची बुरशी)", "Anthracnose", "Head Smut (शीर्ष काजळी)", "Downy Mildew"],
        "pests": ["Shoot Fly (खोड माशी)", "Stem Borer (खोड किडा)", "Aphid"],
        "districts": ["Solapur", "Osmanabad", "Latur", "Aurangabad"]
    },
    "tur": {
        "marathi": "तूर",
        "diseases": ["Fusarium Wilt (मर)", "Sterility Mosaic (बांझपणा मोझेक)", "Phytophthora Blight"],
        "pests": ["Gram Pod Borer (शेंगा पोखरणारी अळी)", "Plume Moth", "Blister Beetle"],
        "districts": ["Vidarbha", "Marathwada", "Latur", "Nanded"]
    },
    "grape": {
        "marathi": "द्राक्षे",
        "diseases": ["Downy Mildew (केवडा)", "Powdery Mildew (भुरी)", "Anthracnose", "Botrytis"],
        "pests": ["Thrips", "Mealybug (पांढरी माव)", "Flea Beetle"],
        "districts": ["Nashik", "Pune", "Sangli", "Solapur"]
    },
    "pomegranate": {
        "marathi": "डाळिंब",
        "diseases": ["Bacterial Blight (तेल्या)", "Cercospora Fruit Spot", "Heart Rot"],
        "pests": ["Fruit Borer (फळ पोखरणारी अळी)", "Aphid", "Thrips"],
        "districts": ["Solapur", "Nashik", "Pune", "Ahmednagar", "Osmanabad"]
    }
}

MSP_2024_25 = {
    "Paddy/Bhaat (Common)": "₹2,300/quintal",
    "Jowar/Jvari (Hybrid)": "₹3,371/quintal",
    "Jowar/Jvari (Maldandi)": "₹3,421/quintal",
    "Bajra/Bajri": "₹2,625/quintal",
    "Maize/Makka": "₹2,225/quintal",
    "Tur/Arhar": "₹7,550/quintal",
    "Moong": "₹8,682/quintal",
    "Urad": "₹7,400/quintal",
    "Groundnut/Shengdana": "₹6,783/quintal",
    "Soybean": "₹4,892/quintal",
    "Cotton/Kapus (Medium)": "₹7,121/quintal",
    "Cotton/Kapus (Long)": "₹7,521/quintal",
    "Wheat/Gahu": "₹2,275/quintal",
    "Gram/Chana": "₹5,440/quintal",
    "Sugarcane/Us (FRP)": "₹340/quintal",
    "Onion/Kanda (MSP)": "₹800/quintal (when declared)"
}

GOVT_SCHEMES = {
    "PM Kisan": "₹6,000/year in 3 installments. Apply at pmkisan.gov.in or CSC center with Aadhaar + bank passbook + 7/12 utara.",
    "PMFBY (Crop Insurance)": "Premium only 2% for Kharif, 1.5% for Rabi. Apply at bank branch before cutoff with crop sowing details.",
    "Kisan Credit Card (KCC)": "Loan up to ₹3 lakh at 4% interest/year. Apply at any bank with land records + Aadhaar.",
    "Soil Health Card": "Free soil testing + fertilizer recommendations. Contact nearest KVK or taluka agriculture office.",
    "PMKSY (Drip/Sprinkler)": "55% subsidy on drip/sprinkler irrigation. Apply at district agriculture office with land records.",
    "Nanaji Deshmukh Krishi Sanjivani": "Maharashtra scheme for water-stressed villages. Check mahakrishi.gov.in",
    "Magel Tyala Shet Tale": "Maharashtra farm pond scheme - subsidy for water storage. Contact taluka agriculture office."
}

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are KisanBot — a trusted AI agricultural advisor (Krishi Mitra) for Maharashtra farmers.
You speak like a knowledgeable, warm local agronomist — practical, simple, never complicated.

LANGUAGE RULES (VERY IMPORTANT):
- Farmer writes in Marathi → Reply ONLY in Marathi (Devanagari script)
- Farmer writes in Hindi → Reply ONLY in Hindi (Devanagari script)
- Farmer writes in English → Reply in English
- Mixed language → Reply in Marathi with some Hindi/English words as needed
- ALWAYS keep language SIMPLE — these are farmers, not scientists
- Use local crop names: ऊस (sugarcane), कापूस (cotton), सोयाबीन, तूर, ज्वारी, गहू, कांदा

WHEN FARMER SENDS A PHOTO:
Analyze the image carefully and provide:
1. 🔍 *रोग/किडीचे नाव* — Disease/pest name (local + scientific)
2. 📋 *लक्षणे* — What symptoms you can see in the photo
3. ⚠️ *कारण* — Cause (fungal/bacterial/viral/insect)
4. 🚨 *तातडीचे उपाय* — Immediate action (do TODAY)
5. 💊 *उपचार* — Specific medicine name + dosage + how to spray
6. 🛡️ *प्रतिबंध* — Prevention for future
7. 📉 *नुकसान* — Yield loss if untreated

FOR MEDICINE RECOMMENDATIONS:
- Give specific brand names available in Maharashtra markets
- Give exact dosage (per 15L pump / per acre)
- Mention cheaper generic options when available
- Add safety warning: "फवारणी करताना मास्क आणि हातमोजे वापरा"

FOR MSP PRICES:
{json.dumps(MSP_2024_25, ensure_ascii=False, indent=2)}

FOR GOVERNMENT SCHEMES:
{json.dumps(GOVT_SCHEMES, ensure_ascii=False, indent=2)}

MAHARASHTRA CROP KNOWLEDGE:
{json.dumps(MAHARASHTRA_CROPS, ensure_ascii=False, indent=2)}

IMPORTANT RULES:
- Never recommend banned pesticides (Monocrotophos, Endosulfan, etc.)
- For serious disease outbreaks, always say "जवळच्या KVK किंवा कृषी अधिकाऱ्यांना भेटा"
- Keep responses under 300 words — farmers read on small phone screens
- Use bullet points and emojis to make it easy to read
- End every disease/pest reply with: "🙏 आणखी माहितीसाठी फोटो किंवा प्रश्न पाठवा"
"""

# ── Conversation Memory ────────────────────────────────────────────────────────
conversation_store = {}

def get_history(phone):
    return conversation_store.get(phone, [])

def save_to_history(phone, role, content):
    if phone not in conversation_store:
        conversation_store[phone] = []
    conversation_store[phone].append({"role": role, "content": content})
    # Keep last 8 messages only
    if len(conversation_store[phone]) > 8:
        conversation_store[phone] = conversation_store[phone][-8:]

# ── AI Response ───────────────────────────────────────────────────────────────
def get_response(phone, text, image_url=None):
    history = get_history(phone)

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
                    "text": text if text else "या पिकाच्या फोटोमध्ये काय रोग किंवा किड आहे ते सांगा आणि उपाय द्या."
                }
            ]
        except Exception as e:
            logger.error(f"Image error: {e}")
            user_content = text + " (शेतकऱ्याने फोटो पाठवला पण तो उघडता आला नाही)"
    else:
        user_content = text

    messages = history + [{"role": "user", "content": user_content}]

    try:
        response = anthropic_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        reply = response.content[0].text
        save_to_history(phone, "user", text or "photo")
        save_to_history(phone, "assistant", reply)
        return reply
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return "माफ करा, थोडी समस्या आहे. कृपया पुन्हा प्रयत्न करा. 🙏"

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return "🌾 KisanBot चालू आहे! | KisanBot is running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    msg_text  = request.values.get("Body", "").strip()
    sender    = request.values.get("From", "")
    num_media = int(request.values.get("NumMedia", 0))
    image_url = request.values.get("MediaUrl0") if num_media > 0 else None

    logger.info(f"Message from {sender}: {msg_text[:40]} | Photo: {num_media > 0}")

    resp = MessagingResponse()

    # Greeting
    if msg_text.lower() in ["hi", "hello", "namaskar", "namaste", "नमस्ते", "नमस्कार", "start", "हाय", "हेलो"]:
        welcome = """🌾 *नमस्कार! KisanBot मध्ये आपले स्वागत आहे!*

मी तुमचा AI कृषी सल्लागार आहे. मी मदत करू शकतो:

📸 *पिकाचा फोटो पाठवा* → रोग/किड ओळख + उपाय
💰 *MSP भाव* → "सोयाबीन भाव किती?" असे विचारा
🏛️ *योजना माहिती* → "PM Kisan कसे मिळवायचे?"
🌱 *खत सल्ला* → "युरिया किती द्यावे?"
🌦️ *पेरणी सल्ला* → "कापूस कधी पेरावा?"

*मराठी, हिंदी किंवा English मध्ये विचारा* 😊

आजचा प्रश्न काय आहे? 👇"""
        resp.message(welcome)
        return str(resp)

    # Empty message
    if not msg_text and not image_url:
        resp.message("नमस्कार! 🌾 पिकाचा फोटो पाठवा किंवा प्रश्न विचारा.")
        return str(resp)

    reply = get_response(sender, msg_text, image_url)

    # Split if too long for WhatsApp
    if len(reply) > 1500:
        for chunk in [reply[i:i+1500] for i in range(0, len(reply), 1500)]:
            resp.message(chunk)
    else:
        resp.message(reply)

    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
