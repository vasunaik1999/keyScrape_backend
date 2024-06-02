from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import tldextract
import re
import yake

app = Flask(__name__)

# Specify User Agent
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3538.102 Safari/537.36 Edge/18.19582"
}

# Initialize the YAKE keyword extractor
kw_extractor = yake.KeywordExtractor()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        keyword = request.form['keyword']

        try:
            # Scrape data based on the keyword
            scraped_data = scrape_google(keyword)

            # Extract keywords from the combined content
            combined_content = combine_content(scraped_data)
            keywords = extract_keywords(combined_content)

            # Render the results template with the scraped data and extracted keywords
            return render_template('results.html', keyword=keyword, data=scraped_data, keywords=keywords)

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            return render_template('error.html', error_message=error_message)

    return render_template('index.html')


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

def extract_keywords(text):
    # Extract keywords from the combined text using YAKE
    keywords = kw_extractor.extract_keywords(text)
    return keywords

if __name__ == '__main__':
    app.run(debug=True)
