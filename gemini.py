from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import requests
from keys import API_KEY, CURRENCY_API_KEY, STOCK_API_KEY

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

app = Flask(__name__)

CURRENCY_API_URL = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/pair"

STOCK_API_URL = "https://www.alphavantage.co/query"

CRYPTO_API_URL = "https://api.coingecko.com/api/v3/simple/price"

def convert_currency(amount, from_currency, to_currency):
    url = f"{CURRENCY_API_URL}/{from_currency}/{to_currency}/{amount}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("conversion_result")
    else:
        return None

def get_stock_price(symbol):
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": STOCK_API_KEY,
    }
    response = requests.get(STOCK_API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get("Global Quote", {}).get("05. price")
    else:
        return None

def get_crypto_price(coin_id, currency="usd"):
    params = {
        "ids": coin_id,
        "vs_currencies": currency,
    }
    response = requests.get(CRYPTO_API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get(coin_id, {}).get(currency)
    else:
        return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("user_input")
    
    if "convert" in user_input.lower() and "to" in user_input.lower():
        try:
            parts = user_input.split()
            amount = float(parts[1])
            from_currency = parts[2].upper()
            to_currency = parts[4].upper()
            result = convert_currency(amount, from_currency, to_currency)
            if result:
                return jsonify({"response": f"{amount} {from_currency} = {result} {to_currency}"})
            else:
                return jsonify({"response": "Sorry, I couldn't convert the currency."})
        except:
            return jsonify({"response": "Invalid currency conversion request. Please try again."})

    elif "stock price" in user_input.lower():
        try:
            symbol = user_input.split()[-1].upper()
            price = get_stock_price(symbol)
            if price:
                return jsonify({"response": f"The current price of {symbol} is ${price}."})
            else:
                return jsonify({"response": f"Sorry, I couldn't fetch the price for {symbol}."})
        except:
            return jsonify({"response": "Invalid stock symbol. Please try again."})

    elif "crypto price" in user_input.lower():
        try:
            coin_id = user_input.split()[-1].lower()
            price = get_crypto_price(coin_id)
            if price:
                return jsonify({"response": f"The current price of {coin_id} is ${price}."})
            else:
                return jsonify({"response": f"Sorry, I couldn't fetch the price for {coin_id}."})
        except:
            return jsonify({"response": "Invalid cryptocurrency ID. Please try again."})

    else:
        response = model.generate_content(user_input)
        return jsonify({"response": response.text})

if __name__ == "__main__":
    app.run(debug=True)
