from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import requests
import logging
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from keys import API_KEY, CURRENCY_API_KEY, STOCK_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini AI
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Initialize Flask app
app = Flask(__name__)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# API URLs
CURRENCY_API_URL = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/pair"
STOCK_API_URL = "https://www.alphavantage.co/query"
CRYPTO_API_URL = "https://api.coingecko.com/api/v3/simple/price"

# In-memory cache for API responses
cache = {}

def cache_response(key, func, *args, **kwargs):
    if key in cache:
        return cache[key]
    result = func(*args, **kwargs)
    cache[key] = result
    return result

# Helper Functions
def convert_currency(amount, from_currency, to_currency):
    url = f"{CURRENCY_API_URL}/{from_currency}/{to_currency}/{amount}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("conversion_result")
    except requests.exceptions.RequestException as e:
        logger.error(f"Currency conversion error: {e}")
        return None

def get_stock_price(symbol):
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": STOCK_API_KEY,
    }
    try:
        response = requests.get(STOCK_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("Global Quote", {}).get("05. price")
    except requests.exceptions.RequestException as e:
        logger.error(f"Stock price fetch error: {e}")
        return None

def get_crypto_price(coin_id, currency="usd"):
    params = {
        "ids": coin_id,
        "vs_currencies": currency,
    }
    try:
        response = requests.get(CRYPTO_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get(coin_id, {}).get(currency)
    except requests.exceptions.RequestException as e:
        logger.error(f"Crypto price fetch error: {e}")
        return None

# Routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
@limiter.limit("10 per minute")
def chat():
    user_input = request.form.get("user_input").strip().lower()

    # Currency Conversion
    if "convert" in user_input and "to" in user_input:
        try:
            parts = user_input.split()
            amount = float(parts[1])
            from_currency = parts[2].upper()
            to_currency = parts[4].upper()
            cache_key = f"convert_{amount}_{from_currency}_{to_currency}"
            result = cache_response(cache_key, convert_currency, amount, from_currency, to_currency)
            if result:
                return jsonify({"response": f"{amount} {from_currency} = {result:.2f} {to_currency}"})
            else:
                return jsonify({"response": "Sorry, I couldn't convert the currency. Please check the currencies and try again."})
        except (IndexError, ValueError):
            return jsonify({"response": "Invalid currency conversion request. Please use the format: 'convert 100 USD to EUR'."})

    # Stock Price
    elif "stock price" in user_input:
        try:
            symbol = user_input.split()[-1].upper()
            cache_key = f"stock_{symbol}"
            price = cache_response(cache_key, get_stock_price, symbol)
            if price:
                return jsonify({"response": f"The current price of {symbol} is ${price}."})
            else:
                return jsonify({"response": f"Sorry, I couldn't fetch the price for {symbol}. Please check the stock symbol and try again."})
        except IndexError:
            return jsonify({"response": "Invalid stock symbol. Please use the format: 'stock price AAPL'."})

    # Cryptocurrency Price
    elif "crypto price" in user_input:
        try:
            coin_id = user_input.split()[-1].lower()
            cache_key = f"crypto_{coin_id}"
            price = cache_response(cache_key, get_crypto_price, coin_id)
            if price:
                return jsonify({"response": f"The current price of {coin_id} is ${price}."})
            else:
                return jsonify({"response": f"Sorry, I couldn't fetch the price for {coin_id}. Please check the cryptocurrency ID and try again."})
        except IndexError:
            return jsonify({"response": "Invalid cryptocurrency ID. Please use the format: 'crypto price bitcoin'."})

    # General Chat
    else:
        try:
            response = model.generate_content(user_input)
            return jsonify({"response": response.text})
        except Exception as e:
            logger.error(f"Gemini AI error: {e}")
            return jsonify({"response": "Sorry, I encountered an error while processing your request. Please try again."})

# User Authentication
users = {}

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    if email in users and users[email] == password:
        return jsonify({"success": True, "message": "Login successful!"})
    else:
        return jsonify({"success": False, "message": "Invalid email or password."})

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    if email in users:
        return jsonify({"success": False, "message": "Email already registered."})
    else:
        users[email] = password
        return jsonify({"success": True, "message": "Signup successful!"})

# Run the Flask app
#if __name__ == "__main__":
   # app.run(debug=True)
