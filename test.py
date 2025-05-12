import os
from twilio.rest import Client # type: ignore
from dotenv import load_dotenv # type: ignore

load_dotenv()
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

message = client.messages.create(
    from_=os.getenv("TWILIO_WHATSAPP_FROM"),
    to=os.getenv("TWILIO_WHATSAPP_TO"),
    body="Hello Nakama! 🌟 This is a test from your Twilio WhatsApp sandbox."
)

print("Sent message SID:", message.sid)
