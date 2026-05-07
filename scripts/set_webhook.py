import urllib.request
import json

TOKEN = "8534227633:AAEqULwA8rypkF-BW87G_9ACmKWNEoGZFI4"
# Using Vercel as it is currently the working backend with Python
WEBHOOK_URL = "https://media-seven-eta.vercel.app/api"

def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read().decode('utf-8')
            print(data)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    set_webhook()
