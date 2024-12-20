from flask import Flask, request, jsonify
from flask_cors import CORS
import spacy
from database import fetch_products, fetch_faq
from dotenv import load_dotenv
import os
import requests
import pandas as pd
from transformers import pipeline

# Load environment variables from .env
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize NLP model
nlp = spacy.load("en_core_web_sm")

# Sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis")

# Your Gemini API Key (from .env file)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# In-memory session storage
user_sessions = {}

def fetch_gemini_data(prompt):
    """Fetch data from Gemini API using API key."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=" + GEMINI_API_KEY

    # Prepare request payload
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
        response_data = response.json()

        if "candidates" in response_data and len(response_data["candidates"]) > 0:
            return response_data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "No response from Gemini API."

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Gemini data: {e}")
        return "An error occurred while processing your request."

def is_greeting(user_input):
    """Check if the user input is a greeting."""
    greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy"]
    return any(greet in user_input.lower() for greet in greetings)

def analyze_sentiment(user_input):
    """Analyze sentiment of the user input."""
    result = sentiment_analyzer(user_input)[0]
    return result['label'], result['score']

def parse_query(user_input):
    """Parses user input to identify query components."""
    doc = nlp(user_input.lower())
    tokens = [token.text for token in doc]

    filters = {
        "gender": None,
        "skin_type": None,
        "category": None,
        "price_min": None,
        "price_max": None,
        "hair_type": None
    }

    if "male" in tokens:
        filters["gender"] = "male"
    elif "female" in tokens:
        filters["gender"] = "female"
    elif "unisex" in tokens or "all genders" in tokens:
        filters["gender"] = "unisex"

    skin_types = ["dry skin", "oily skin", "sensitive skin", "normal skin"]
    for skin in skin_types:
        if skin in user_input.lower():
            filters["skin_type"] = skin

    hair_types = ["dry hair", "oily hair", "curly hair", "straight hair", "frizzy hair", "normal hair"]
    for hair in hair_types:
        if hair in user_input.lower():
            filters["hair_type"] = hair

    categories = ["soap", "cleanser", "shower gel", "cream", "perfume", "lipstick", "body lotion", 
                  "haircare", "mascara", "blush", "serum", "face oil", "contour", "bb cream", "exfoliator", 
                  "eyeliner", "concealer", "cc cream", "face mask", "bronzer", "primer", "makeup remover", 
                  "powder", "eye shadow", "lip liner", "foundation", "setting spray", "deodorant", "body wash"]
    for category in categories:
        if category in tokens:
            filters["category"] = category
            break

    words = user_input.split()
    for i, word in enumerate(words):
        if word.lstrip('$').replace('.', '').isdigit():
            price = float(word.lstrip('$'))
            if i > 0 and words[i-1] == "under":
                filters["price_max"] = price
            else:
                filters["price_min"] = price

    return filters

def format_products_response(products, query_type):
    """Format product data into a more readable response."""
    if not products:
        return "Sorry, I couldn't find any products that match your query."

    response = f"Here are the top {len(products)} {query_type}:
"
    for idx, product in enumerate(products[:10]):
        response += f"\n{idx + 1}. **{product['name']}** by {product['brand']}\n"
        response += f"   Price: ${product['price']}\n"
        response += f"   Description: {product['description']}\n"
        if query_type == "cream" and product.get("skin_type"):
            response += f"   Skin Type: {product['skin_type']}\n"
        if query_type == "shampoo" and product.get("hair_type"):
            response += f"   Hair Type: {product['hair_type']}\n"
        response += "-" * 40

    return response

def chatbot_response(user_input, session_id):
    """Handles the chatbot's response."""
    try:
        if session_id not in user_sessions:
            user_sessions[session_id] = {"context": {}}

        session_context = user_sessions[session_id]

        if is_greeting(user_input):
            return {"reply": "Hello! How can I assist you today? 😊"}

        sentiment_label, sentiment_score = analyze_sentiment(user_input)

        if sentiment_label == "NEGATIVE":
            empathy_response = "I'm here to help. Let me know how I can assist you."
        elif sentiment_label == "POSITIVE":
            empathy_response = "I'm glad to hear that! How can I assist further?"
        else:
            empathy_response = "Got it. How can I help you today?"

        products = None
        product_keywords = ["products", "available products", "give products", "what products", "show me products"]
        if any(keyword in user_input.lower() for keyword in product_keywords):
            filters = parse_query(user_input)
            products = fetch_products(
                category=filters.get("category"),
                skin_type=filters.get("skin_type"),
                gender=filters.get("gender"),
                price_min=filters.get("price_min"),
                price_max=filters.get("price_max")
            )
            if products:
                query_type = filters.get("category", "products")
                response = format_products_response(products, query_type)
                return {"reply": response}

        if not products:
            faq_answer = fetch_faq(user_input)
            if faq_answer:
                return {"reply": faq_answer}

        gemini_response = fetch_gemini_data(user_input)
        if gemini_response:
            return {"reply": gemini_response}

        return {"reply": "I'm sorry, I couldn't find any relevant information. Could you try rephrasing your query?"}

    except Exception as e:
        print(f"Error handling request: {e}")
        return {"reply": "An error occurred while processing your request."}

@app.route('/chat', methods=['POST'])
def chat():
    """Handles the user input and returns a response."""
    try:
        data = request.json
        user_input = data.get("userInput")
        session_id = data.get("sessionId")

        if not user_input:
            return jsonify({"reply": "No input received. Please type something."})

        response = chatbot_response(user_input, session_id)
        return jsonify(response)

    except Exception as e:
        print(f"Error handling request: {e}")
        return jsonify({"reply": "An error occurred while processing your request."})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
