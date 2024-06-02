from flask import Flask, render_template, request,  jsonify
import requests
from bs4 import BeautifulSoup
import tldextract
import re
import yake
from rake_nltk import Rake
import nltk
from keybert import KeyBERT
import google.generativeai as genai
import json
import markdown
from flask_cors import CORS
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash


genai.configure(api_key='AIzaSyDKdXqhB75jkxHNTkXwZkem2hTYilseOJ8')

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
# Specify User Agent
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3538.102 Safari/537.36 Edge/18.19582"
}

# Initialize the YAKE keyword extractor
kw_extractor = yake.KeywordExtractor()


ARTICLES_FILE = 'articles.json'
KEYWORDS_FILE = 'keywords.json'
USERS_FILE = 'users.json'

# Ensure the users JSON file exists
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as file:
        json.dump([], file)

# Ensure the JSON files exist
if not os.path.exists(ARTICLES_FILE):
    with open(ARTICLES_FILE, 'w') as file:
        json.dump([], file)

if not os.path.exists(KEYWORDS_FILE):
    with open(KEYWORDS_FILE, 'w') as file:
        json.dump([], file)


def read_keywords_file():
    try:
        with open('keywords.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []
    
def write_keywords_file(data):
    with open('keywords.json', 'w') as file:
        json.dump(data, file, indent=4)

def get_next_id(data):
    if not data:
        return 1
    else:
        return max(item['id'] for item in data) + 1
    
@app.route('/', methods=['POST'])
def index():
    try:
        if request.method == 'POST':
            data = request.json  # Get the JSON data from the request
            keyword = data.get('keyword')
            algo = data.get('algorithm')
            user_id = data.get('user_id')
            algorithm = algo['value']
            no_of_keywords = int(data.get('no_of_keywords'))

            # Scrape data based on the keyword
            scraped_data = scrape_google(keyword)

            # Extract keywords from the combined content
            combined_content = combine_content(scraped_data)

            if algorithm == "Yake":            
                keywords = extract_keywords_yake(combined_content, no_of_keywords)
            elif algorithm == "KeyBERT":
                keywords = extract_keywords_keybert(combined_content, no_of_keywords)
            else:
                keywords = extract_keywords_rake(combined_content, no_of_keywords)


            # Store data in a JSON file
            # user_id = 1  # Hardcoded for now
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # keywords_data = {
            #     "user_id": user_id,
            #     "keyword": keyword,
            #     "algorithm": algorithm,
            #     "no_of_keywords": no_of_keywords,
            #     "keywords": [kw[0] for kw in keywords],  # Only store the keywords, not the scores
            #     "timestamp": timestamp
            # }

            # Read existing data
            existing_data = read_keywords_file()
            next_id = get_next_id(existing_data)
            # Append new data
            keywords_data = {
                "id": next_id,
                "user_id": user_id,
                "keyword": keyword,
                "algorithm": algorithm,
                "no_of_keywords": no_of_keywords,
                "keywords": [kw[0] for kw in keywords],  # Only store the keywords, not the scores
                "timestamp": timestamp
            }

            # Append new data
            existing_data.append(keywords_data)
            # Write updated data back to file
            write_keywords_file(existing_data)

            # Prepare data for JSON response
            response_data = {
                'keyword': keyword,
                'data': scraped_data,
                'keywords': keywords,
                'algorithm': algorithm,
                'keyword_id': next_id,
            }

            return jsonify(response_data)
    
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500
    
# @app.route('/keywords', methods=['GET'])
# def get_keywords():
#     try:
#         data = read_keywords_file()
#         return jsonify(data)
#     except Exception as e:
#         error_message = f"An error occurred: {str(e)}"
#         return jsonify({'error': error_message}), 500

@app.route('/keywords', methods=['GET', 'POST'])
def get_keywords():
    try:
        user_id = request.json.get('user_id')
        data = read_keywords_file()

        # Filter the data based on user_id
        filtered_data = [entry for entry in data if entry.get('user_id') == int(user_id)]
        
        return jsonify(filtered_data)
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500

@app.route('/keywords/<int:keywords_id>', methods=['GET'])
def get_keywords_by_id(keywords_id):
    try:
        user_id = request.args.get('user_id')
        print(keywords_id)
        print(user_id)
        data = read_json_file('keywords.json')
        keywords = next((entry for entry in data if entry.get('id') == keywords_id and entry.get('user_id') == int(user_id)), None)
        print(keywords)
        if keywords:
            return jsonify(keywords)
        else:
            return jsonify({'error': 'keyword not found or user does not have access'}), 404
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500

def scrape_google(keyword):
    payload = {'q': keyword}
    html = requests.get("https://www.google.com/search", params=payload, headers=headers)
    html.raise_for_status()  # Raise an HTTPError for bad response status
    data = []

    response = html.text
    soup = BeautifulSoup(response, 'html.parser')

    for container in soup.find_all('div', class_='Gx5Zad fP1Qef xpd EtOod pkphOe'):
        try:
            web_title = container.find('div', class_='BNeawe vvjwJb AP7Wnd UwRFLe').text
        except AttributeError:
            web_title = 'N/A'

        try:
            link_tag = container.find('div', class_='egMi0 kCrYT').find('a')
            long_link = link_tag["href"]

            # Extract the URL using regex
            match = re.search(r"&url=(.*?)&", long_link)

            if match:
                link = match.group(1)

                # Send a GET request to the webpage
                response1 = requests.get(link)

                response1.raise_for_status()  # Raise an HTTPError for bad response status

                # Parse the HTML content of the webpage using BeautifulSoup
                soup1 = BeautifulSoup(response1.content, 'html.parser')

                # Find all <p> tags within the webpage
                paragraph_tags = soup1.find_all('p')

                # Extract the content of each <p> tag
                paragraph_content = [tag.get_text() for tag in paragraph_tags]

                # Save the content to a dictionary
                data.append({
                    'title': web_title,
                    'link': link,
                    'content': paragraph_content
                })

        except Exception as e:
            print("Error:", e)

    return data


def combine_content(scraped_data):
    combined_content = ""
    for entry in scraped_data:
        combined_content += ' '.join(entry['content']) + ' '
    return combined_content

def extract_keywords_yake(text, no_of_keywords):
    # Extract keywords from the combined text using YAKE
    keywords = kw_extractor.extract_keywords(text)
      # Limit the number of keywords to the specified number
    selected_keywords = keywords[:no_of_keywords]

    return selected_keywords

def extract_keywords_rake(text, no_of_keywords):
    nltk.download('stopwords')
    nltk.download('punkt')

    significant_keywords = []
    
    r = Rake()
    r.extract_keywords_from_text(text)

    for rating, keyword in r.get_ranked_phrases_with_scores():
        if rating > 10:
            significant_keywords.append((keyword, rating))

    selected_keywords = significant_keywords[:no_of_keywords]

    return selected_keywords

def extract_keywords_keybert(text, no_of_keywords):
    print("Hello, console!", no_of_keywords)
    kw_model = KeyBERT()

    # Extract keywords using KeyBERT
    keywords = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 3),
        stop_words='english',
        use_mmr=True,
        diversity=0.6,
        top_n=no_of_keywords
    )
    
    # Print extracted keywords to console for debugging
    print("Extracted Keywords:", keywords)
    
    return keywords   

# Function to read JSON file
def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []
    return data

# Function to write to JSON file
def write_json_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/generate_article', methods=['POST'])
def generate_article():
    try:
        keywords = request.json.get('keywords')
        keyword = request.json.get('keyword')
        algorithm = request.json.get('algorithm')
        keyword_id = request.json.get('keyword_id')
        user_id = request.json.get('user_id')

        # Join keywords into a single string
        keyword_text = ', '.join(keywords)
        prompt = f"Generate an informative article on the {keyword} using these keywords: {keyword_text}. Ensure the keywords are naturally incorporated into the text."

        # Generate content using the Gemini API (mocked here for illustration)
        response = genai.GenerativeModel('gemini-pro').generate_content(prompt)
        article_text = response.text.strip()
        formatted_article = markdown.markdown(article_text)

        # Read existing articles
        articles = read_json_file('articles.json')
        new_id = len(articles) + 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Create new article entry
        new_article = {
            'id': new_id,
            'user_id': user_id,
            'search_term': keyword,
            'article': formatted_article,
            'keywords_id': keyword_id,
            'datetime': timestamp
        }

        # Append new article and save
        articles.append(new_article)
        write_json_file('articles.json', articles)

        return jsonify(new_article)
    
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500

@app.route('/articles', methods=['GET','POST'])
def get_articles():
    try:
        user_id = request.json.get('user_id')
        data = read_json_file('articles.json')
        articles = [entry for entry in data if entry.get('user_id') == int(user_id)]
        
        return jsonify(articles)
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500

# @app.route('/article/<int:article_id>', methods=['GET'])
# def get_article_by_id(article_id):
#     try:
#         data = read_json_file('articles.json')
#         article = next((entry for entry in data if entry.get('id') == article_id), None)
#         if article:
#             return jsonify(article)
#         else:
#             return jsonify({'error': 'Article not found'}), 404
#     except Exception as e:
#         error_message = f"An error occurred: {str(e)}"
#         return jsonify({'error': error_message}), 500

@app.route('/article/<int:article_id>', methods=['GET'])
def get_article_by_id(article_id):
    try:
        user_id = request.args.get('user_id')
        print(user_id)
        data = read_json_file('articles.json')
        article = next((entry for entry in data if entry.get('id') == article_id and entry.get('user_id') == int(user_id)), None)
        print(article)
        if article:
            return jsonify(article)
        else:
            return jsonify({'error': 'Article not found or user does not have access'}), 404
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500

@app.route('/update-article', methods=['POST'])
def update_article():
    try:
        article_id = request.json.get('article_id')
        content = request.json.get('content')
        print(article_id, content)
        print("before ua")
        # Update the article content in the JSON file
        update_article_content(article_id, content)
        
        return jsonify({'message': 'Article content updated successfully!'})
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'error': error_message}), 500

def update_article_content(article_id, content):
    try:
        print("ua")
        with open('articles.json', 'r') as file:
            articles = json.load(file)
        
        for article in articles:
            if article['id'] == article_id:
                article['article'] = content
                break
        
        with open('articles.json', 'w') as file:
            json.dump(articles, file, indent=4)
        
        print("done")
    except Exception as e:
        raise e 

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        password_confirmation = data.get('password_confirmation')

        if not all([name, email, password, password_confirmation]):
            return jsonify({'message': 'All fields are required.'}), 400

        if password != password_confirmation:
            return jsonify({'message': 'Passwords do not match.'}), 400

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Read existing users
        with open(USERS_FILE, 'r') as file:
            users = json.load(file)

        # Check if the email is already registered
        if any(user['email'] == email for user in users):
            return jsonify({'message': 'Email is already registered.'}), 400

        # Generate a unique ID for the new user
        new_id = max([user['id'] for user in users], default=0) + 1

        # Create a new user entry
        new_user = {
            'id': new_id,
            'name': name,
            'email': email,
            'password': hashed_password
        }

        # Append the new user to the list and save
        users.append(new_user)
        with open(USERS_FILE, 'w') as file:
            json.dump(users, file)

        return jsonify({'message': 'Registration successful!'}), 201

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'message': error_message}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not all([email, password]):
            return jsonify({'message': 'Email and password are required.'}), 400

        # Read existing users
        with open(USERS_FILE, 'r') as file:
            users = json.load(file)

        # Find the user by email
        user = next((user for user in users if user['email'] == email), None)

        if not user or not check_password_hash(user['password'], password):
            return jsonify({'message': 'Invalid email or password.'}), 401

        user_data = {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
        }

        return jsonify({'message': 'Login successful!', 'user': user_data}), 200

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return jsonify({'message': error_message}), 500


if __name__ == '__main__':
    app.run(debug=True)
