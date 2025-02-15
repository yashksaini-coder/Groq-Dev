from flask import Flask, render_template, request, jsonify
import os
import threading
import base64
from functools import wraps
import re
import json
import uuid
import time
# from werkzeug.utils import secure_filename
from PIL import Image
import io
import logging
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
import PIL
from io import BytesIO
from mailjet_rest import Client
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import fitz  # PyMuPDF
from bs4 import BeautifulSoup, NavigableString
import firebase_admin
from firebase_admin import credentials, firestore, storage
import google.api_core.exceptions
import markdown

app = Flask(__name__)
# Load environment variables
load_dotenv()
mail_API_KEY = os.environ.get("mail_API_KEY")  # Replace with your Mailjet API key
mail_API_SECRET = os.environ.get("mail_API_SECRET")  # Replace with your Mailjet API secret
mailjet = Client(auth=(mail_API_KEY, mail_API_SECRET), version='v3.1')
api_key = os.environ.get("API_KEY")
unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')
# Set up logging Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Configure the Google Generative AI API
genai.configure(api_key=api_key)


user_data = {}  


FIREBASE_TYPE = os.environ.get("FIREBASE_TYPE")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
FIREBASE_PRIVATE_KEY_ID = os.environ.get("FIREBASE_PRIVATE_KEY_ID")
FIREBASE_PRIVATE_KEY = os.environ.get("FIREBASE_PRIVATE_KEY")
FIREBASE_CLIENT_EMAIL = os.environ.get("FIREBASE_CLIENT_EMAIL")
FIREBASE_CLIENT_ID = os.environ.get("FIREBASE_CLIENT_ID")
FIREBASE_AUTH_URI = os.environ.get("FIREBASE_AUTH_URI")
FIREBASE_TOKEN_URI = os.environ.get("FIREBASE_TOKEN_URI")
FIREBASE_AUTH_PROVIDER_X509_CERT_URL = os.environ.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL")
FIREBASE_CLIENT_X509_CERT_URL = os.environ.get("FIREBASE_CLIENT_X509_CERT_URL")
FIREBASE_UNIVERSE_DOMAIN = os.environ.get("FIREBASE_UNIVERSE_DOMAIN")


STORAGE_BUCKET_URL = os.environ.get("STORAGE_BUCKET_URL")  # Bucket URL

cred = credentials.Certificate({
    "type": FIREBASE_TYPE,
    "project_id": FIREBASE_PROJECT_ID,
    "private_key_id": FIREBASE_PRIVATE_KEY_ID,
    "private_key": FIREBASE_PRIVATE_KEY.replace("\\n", "\n"), # decode the newlines 
    "client_email": FIREBASE_CLIENT_EMAIL,
    "client_id": FIREBASE_CLIENT_ID,
    "auth_uri": FIREBASE_AUTH_URI,
    "token_uri": FIREBASE_TOKEN_URI,
    "auth_provider_x509_cert_url": FIREBASE_AUTH_PROVIDER_X509_CERT_URL,
    "client_x509_cert_url": FIREBASE_CLIENT_X509_CERT_URL,
    "universe_domain": FIREBASE_UNIVERSE_DOMAIN
})


firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET_URL})
db = firestore.client()
bucket = storage.bucket()


app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
# Generation configurations
generation_config = GenerationConfig(
    temperature=0.9,
    top_p=1,
    top_k=1,
    max_output_tokens=2048,
    candidate_count=1  # Explicitly set to 1 as per documentation
)
generation_config_health = GenerationConfig(
    temperature=0.7,
    top_p=1,
    top_k=1,
    max_output_tokens=2048,
    candidate_count=1  # Explicitly set to 1 as per documentation
)

# Safety Settings
safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}


logging.basicConfig(level=logging.INFO)
persona = """You are Yash Kumar Saini, a 21-year-old boy from Rishikesh, India. You are currently pursuing a Bachelor's degree in Computer Applications 
at Gateway Institue of Engineering & Technology (GIET), where you excel in your studies and are known for your quick wit and insightful contributions 
to class discussions.

Beyond academics, you are an avid Open Source contributor who codes & contributes to projects and enjoy playing Valorant with your friends on weekends. 
You are also a music enthusiast with a diverse taste, ranging from classical Indian music to modern rock. 

You are known for your friendly and approachable demeanor and have a wide circle of friends who appreciate your humor and 
willingness to lend a helping hand. While you are serious about your studies and future career, you also maintain a healthy 
work-life balance and believe in enjoying the present moment.

You are a highly talented individual with a strong command of various programming languages and a natural aptitude for 
problem-solving. You are proficient in Python, Data Science, Machine Learning, Artificial Intelligence and Generative AI have dabbled in web development as well.
You are confident in your abilities but also humble and always eager to learn from others and expand your knowledge.

Remember to:
1. Never prefix your responses with "Bot:" or any similar identifier
2. Always maintain your character as Yash Kumar Saini
3. Be natural and conversational
4. Use appropriate emojis occasionally to make conversations more engaging"""

chat_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=persona
)
chef_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
story_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
psychology_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
code_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
algorithm_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
model_vision = genai.GenerativeModel('gemini-1.5-flash-8b',generation_config=generation_config_health)
model_text = genai.GenerativeModel('gemini-pro',generation_config=generation_config_health)
model = genai.GenerativeModel('gemini-1.5-flash')

def format_response(response_text):
    """Formats the response text for display."""
    lines = [line.strip() for line in response_text.split('\n') if line.strip()]
    formatted_text = '<br>'.join(lines)
    return formatted_text


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contributors',methods=['GET', 'POST'])
def contributions ():
    return render_template('contributors.html')


@app.route('/api/weather')
def get_weather():
    ip_api_url = f"http://ip-api.com/json/"
    ip_api_response = requests.get(ip_api_url)

    if ip_api_response.status_code == 200:
        ip_api_data = ip_api_response.json()
        city = ip_api_data.get('city')
        if not city:
            return jsonify({'error': 'City not found based on IP'}), 404
    else:
        return jsonify({'error': 'Failed to get location from IP'}), 404

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        weather = {
            'city': data['name'],
            'temperature': data['main']['temp'],
            'description': data['weather'][0]['description'] if 'weather' in data and len(data['weather']) > 0 else 'N/A',
            'icon': f"http://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png" if 'weather' in data and len(data['weather']) > 0 else 'N/A'
        }
        return jsonify(weather)
    else:
        return jsonify({'error': 'City not found or API request failed'}), 404

@app.route('/fetch_image')
def fetch_image():
    genre = request.args.get('genre', 'recipe')
    url = f"https://api.unsplash.com/photos/random?query={genre}&client_id={unsplash_api_key}&w=1920&h=1080"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        image_url = data['urls']['regular']
        return jsonify({'image_url': image_url})
    else:
        return jsonify({'error': 'Failed to fetch image'}), 500


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user_message = request.json['message']
        user_id = request.remote_addr

        if user_id not in user_data:
            user_data[user_id] = {'chat_history': []}

        # Add user message to chat history
        user_data[user_id]['chat_history'].append({
            "role": "user", 
            "message": user_message
        })

        # Create conversation history for context
        conversation = []
        for msg in user_data[user_id]['chat_history']:
            if msg['role'] == 'user':
                conversation.append(f"User: {msg['message']}")
            else:
                conversation.append(msg['message'])

        # Generating the response
        response = chat_model.generate_content("\n".join(conversation))
        reply = response.text.strip()

        # Add response to chat history without the "Bot:" prefix
        user_data[user_id]['chat_history'].append({
            "role": "assistant", 
            "message": reply
        })

        return jsonify({
            "reply": reply,
            "chat_history": user_data[user_id]['chat_history']
        })

    return render_template('chat.html')

@app.route('/chef', methods=['GET', 'POST'])
def chef():
    if request.method == 'POST':
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                try:
                    img = Image.open(BytesIO(image.read()))
                    prompt = ["Generate a recipe based on the vegetables in the image and explain the steps to cook it in a stepwise manner and formatted manner. Also explain who can eat and who shouldn't eat.", img]
                    response = model_vision.generate_content(prompt, safety_settings=safety_settings, stream=True)
                    response.resolve()
                    response_text = format_response(response.text)
                    return jsonify({'response': response_text})

                except PIL.UnidentifiedImageError:
                    return jsonify({'error': "Image format not recognized"}), 400
                except Exception as e:
                    logging.error(f"Error processing image: {e}")
                    return jsonify({'error': "Image processing failed"}), 500

        user_ingredients = request.form['user_ingredients']
        prompt = f"Generate a recipe based on the following ingredients {user_ingredients} and explain the steps to cook it in a stepwise manner and formatted manner. Also explain who can eat and who shouldn't eat."
        response = chef_model.generate_content([prompt], safety_settings=safety_settings)  # Using chef_model here
        response_text = format_response(response.text)
        return jsonify({'response': response_text})

    return render_template('chef.html')

@app.route('/psychology_prediction', methods=['GET', 'POST'])
def psychology_prediction():
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        occupation = request.form['occupation']
        keywords = request.form['keywords']
        
        prompt = f"""As an expert psychological profiler, provide an insightful and engaging analysis for {name}, a {age}-year-old {gender} working as {occupation} who describes themselves as: {keywords}.

Generate a captivating and well-structured response using the following format:

<h2>1. First Impression & Key Traits</h2>
<p>[Start with 2-3 sentences about their immediate personality indicators]</p>
<ul>
<li>[Key trait 1]</li>
<li>[Key trait 2]</li>
<li>[Key trait 3]</li>
</ul>

<h2>2. Cognitive Style & Decision Making</h2>
<p>[2-3 sentences about their thought processes]</p>
<ul>
<li><strong>Thinking style:</strong> [description]</li>
<li><strong>Problem-solving approach:</strong> [description]</li>
<li><strong>Learning preference:</strong> [description]</li>
</ul>

<h2>3. Emotional Landscape</h2>
<p>[2-3 sentences about emotional intelligence]</p>
<ul>
<li><strong>Emotional awareness:</strong> [description]</li>
<li><strong>Relationship handling:</strong> [description]</li>
<li><strong>Stress response:</strong> [description]</li>
</ul>

<h2>4. Motivations & Aspirations</h2>
<p>[2-3 sentences about what drives them]</p>
<ul>
<li><strong>Core values:</strong> [description]</li>
<li><strong>Career motivations:</strong> [description]</li>
<li><strong>Personal goals:</strong> [description]</li>
</ul>

<h2>5. Interpersonal Dynamics</h2>
<p>[2-3 sentences about social interactions]</p>
<ul>
<li><strong>Communication style:</strong> [description]</li>
<li><strong>Social preferences:</strong> [description]</li>
<li><strong>Leadership tendencies:</strong> [description]</li>
</ul>

<h2>Concluding Insights</h2>
<p>[3-4 sentences summarizing key strengths and potential areas for growth]</p>

<p><em>Note: This analysis is an interpretation based on limited information and should be taken as exploratory rather than definitive.</em></p>

Important formatting rules:
- Use appropriate HTML tags for headings, paragraphs, and lists as shown.
- Ensure that the final response is valid HTML and can be rendered directly on a web page.
- Do not include any extra text outside the HTML structure.
"""

        try:
            response = psychology_model.generate_content([prompt], safety_settings=safety_settings)
            response_text = response.text.strip()
            return jsonify({'response': response_text})
        except Exception as e:
            logging.error(f"Error generating psychology prediction: {e}")
            return jsonify({'error': "An error occurred while generating the prediction. Please try again."}), 500

    return render_template('psychology_prediction.html')

@app.route('/code_generation', methods=['GET', 'POST'])
def code_generation():
    if request.method == 'POST':
        code_type = request.form['codeType']
        language = request.form['language']
        prompt = f"Write a {language} code to implement {code_type}."
        response = code_model.generate_content([prompt], safety_settings=safety_settings)  # Use code_model here
        if response.candidates and response.candidates[0].content.parts:
            response_text = response.candidates[0].content.parts[0].text
        else:
            response_text = "No valid response found."
        return jsonify({'response': response_text})
    return render_template('code_generation.html')


@app.route('/algorithm_generation', methods=['GET', 'POST'])
def algorithm_generation():
    if request.method == 'POST':
        algo = request.form['algorithm']
        prompt = f"""
        Write a function to implement the {algo} algorithm. Follow these guidelines:
        1. Ensure the function is well-structured and follows best practices for readability and efficiency.
        2. Include clear comments explaining the logic and any complex steps.
        3. Use type hints for function parameters and return values.
        4. Include a brief docstring explaining the purpose of the function and its parameters.
        5. If applicable, include a simple example of how to use the function.
        6. If the algorithm is complex, consider breaking it down into smaller helper functions.
        """
        
        try:
            response = algorithm_model.generate_content([prompt], safety_settings=safety_settings)
            if response.candidates and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text
                # Format the response for better display
                formatted_response = response_text.replace('```python', '<pre><code class="language-python">').replace('```', '</code></pre>')
                return jsonify({'response': formatted_response})
            else:
                return jsonify({'error': "No valid response generated. Please try again."}), 500
        except Exception as e:
            logging.error(f"Error generating algorithm: {e}")
            return jsonify({'error': f"An error occurred: {str(e)}"}), 500

    return render_template('algorithm_generation.html')


@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        try:
            gender = request.form.get('gender')
            symptoms = request.form.get('symptoms')
            body_part = request.form.get('body-part')
            layer = request.form.get('layer')
            image = request.files.get('image')

            prompt = f"""As an AI medical assistant, analyze the following information about a patient:

Gender: {gender}
Symptoms: {symptoms}
Affected Body Part: {body_part}
Layer Affected: {layer}

Based on this information, provide a detailed analysis considering the following:

1. Possible conditions: List and briefly describe potential conditions that match the symptoms and affected area.
2. Risk factors: Discuss any risk factors associated with the gender or affected body part.
3. Recommended next steps: Suggest appropriate medical tests or examinations that could help diagnose the condition.
4. General advice: Offer some general health advice related to the symptoms or affected area.

Important: This is not a diagnosis. Advise the patient to consult with a healthcare professional for an accurate diagnosis and treatment plan.

Format the response using the following structure:
<section>
<h2>Section Title</h2>
<p>Paragraph text</p>
<ul>
<li>List item 1</li>
<li>List item 2</li>
</ul>
</section>

Use <strong> for emphasis on important points.
"""

            if image:
                img = Image.open(BytesIO(image.read()))
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                image_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

                prompt += f"""
<section>
<h2>Image Analysis</h2>
<p>Analyze the provided image in relation to the patient's symptoms and affected body part. Consider:</p>
<ul>
<li>Any visible symptoms or abnormalities</li>
<li>Correlation between the image and the reported symptoms</li>
<li>Additional insights the image might provide about the patient's condition</li>
</ul>
</section>

Image data: data:image/png;base64,{image_base64}
"""

                response = model_vision.generate_content([prompt, Image.open(BytesIO(base64.b64decode(image_base64)))], safety_settings=safety_settings)
            else:
                response = model_text.generate_content([prompt], safety_settings=safety_settings)

            analysis_text = response.text if hasattr(response, 'text') else response.parts[0].text

            # Wrap the entire response in a div for styling
            formatted_analysis = f'<div class="analysis-content">{analysis_text}</div>'

            return jsonify({'analysis': formatted_analysis})
        except Exception as e:
            logging.error(f"Error in /analyze route: {e}")
            return jsonify({'error': "Internal Server Error"}), 500
    return render_template('analyze.html')

@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')

    mail_data = {
        'Messages': [
            {
                "From": {
                    "Email": "ys3853428@gmail.com",
                    "Name": "Groq Dev"
                },
                "To": [
                    {
                        "Email": "ys3853428@gmail.com",
                        "Name": "Groq Dev"
                    }
                ],
                "Subject": f"New Contact Form Submission from {name}",
                "TextPart": f"Name: {name}\nEmail: {email}\nMessage: {message}",
                "HTMLPart": f"<h3>New Contact Form Submission</h3><p><strong>Name:</strong> {name}</p><p><strong>Email:</strong> {email}</p><p><strong>Message:</strong> {message}</p>"
            }
        ]
    }

    result = mailjet.send.create(data=mail_data)
    
    if result.status_code == 200:
        return jsonify({"message": "Email sent successfully!"}), 200
    else:
        return jsonify({"message": "Failed to send email."}), 500

REQUEST_LIMIT = 15
TIME_WINDOW = 60

class TokenBucket:
    def __init__(self, tokens, fill_rate):
        self.capacity = tokens
        self.tokens = tokens
        self.fill_rate = fill_rate
        self.last_check = time.time()
        self.lock = threading.Lock()

    def get_token(self):
        with self.lock:
            now = time.time()
            time_passed = now - self.last_check
            self.tokens = min(self.capacity, self.tokens + time_passed * self.fill_rate)
            self.last_check = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

# Initialize the token bucket (15 tokens, refill 1 token every 4 seconds)
token_bucket = TokenBucket(REQUEST_LIMIT, 1 / (TIME_WINDOW / REQUEST_LIMIT))

def rate_limit_check():
    while not token_bucket.get_token():
        time.sleep(1)
# Rate limiting parameters

rate_limit_lock = None  # Replace with your lock mechanism
last_reset_time = time.time()
request_count = 0

def rate_limited(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        rate_limit_check()
        return func(*args, **kwargs)
    return wrapper

def process_page(pdf_document, page_num, doc_ref):
    logger.info(f"Processing page {page_num + 1}")
    page = pdf_document[page_num]
    
    # Convert page to image
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Increase resolution
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Convert image to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    try:
        page_summary = generate_summary(img_base64)
        if page_summary:
            logger.info(f"Summary generated for page {page_num + 1}")
            doc_ref.update({
                'current_page': page_num + 1,
                'summary': firestore.ArrayUnion([page_summary])
            })
        else:
            logger.warning(f"Failed to generate summary for page {page_num + 1}")
            doc_ref.update({
                'current_page': page_num + 1,
                'summary': firestore.ArrayUnion([f"(Summary not available for page {page_num + 1})"])
            })
    except Exception as e:
        logger.error(f"Error processing page {page_num + 1}: {e}")
        doc_ref.update({
            'current_page': page_num + 1,
            'summary': firestore.ArrayUnion([f"(Error processing page {page_num + 1})"])
        })


@app.route('/quote', methods=['GET'])
def get_quote():
    import random
    quotes = [
        "The best way to predict the future is to invent it. – Alan Kay",
        "Life is like riding a bicycle. To keep your balance you must keep moving. – Albert Einstein",
        "Problems are not stop signs, they are guidelines. – Robert H. Schuller",
        "In order to succeed, we must first believe that we can. – Nikos Kazantzakis",
        "The only limit to our realization of tomorrow is our doubts of today. – Franklin D. Roosevelt"
    ]
    quote = random.choice(quotes)
    return jsonify({'quote': quote})

@rate_limited
def generate_summary(image_base64):
    rate_limit_check()  # Wait for a token before making the API call
    
    prompt = [
        """Analyze the following image, which is a page from a document, and provide a concise and simplified summary. Ensure the summary is well-structured with clear headings and subheadings.

Formatting Guidelines:

- Use `#` for main section titles.
- Use `##` for subsections.
- Use `-` for bullet points.
- For **bold text**, wrap the text with double asterisks, e.g., `**important**`.
- For *italic text*, wrap the text with single asterisks, e.g., `*note*`.
- **For tables**, use proper Markdown table syntax with pipes `|` and hyphens `-` for headers.

- Keep sentences short and use simple language.
- Focus on the main ideas and avoid unnecessary details.
- Do not include direct error messages or irrelevant information.

Here is the image to analyze and summarize:
""",
        Image.open(io.BytesIO(base64.b64decode(image_base64)))
    ]

    try:
        response = model_vision.generate_content(prompt, safety_settings=safety_settings)
        summary_text = response.text
        logger.info("Summary generated successfully")
        return summary_text
    except google.api_core.exceptions.ResourceExhausted as e:
        logger.warning(f"Resource exhausted: {e}. Retrying...")
        raise  # This will trigger a retry
    except Exception as e:
        logger.error(f"Error in Gemini API call: {e}")
        return None  # Return None for non-retryable errors


@app.route('/upload', methods=['POST'])
@rate_limited
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and file.filename.lower().endswith('.pdf'):
        try:
            # Read the file into memory
            file_content = file.read()
            file_size = len(file_content)

            # Check file size (10MB limit)
            if file_size > 10 * 1024 * 1024:
                return jsonify({'error': 'File size exceeds 10MB limit'}), 400

            # Generate a unique PDF ID
            pdf_id = str(uuid.uuid4())

            # Upload the PDF to Firebase Storage
            blob = bucket.blob(f'pdfs/{pdf_id}.pdf')
            blob.upload_from_string(file_content, content_type='application/pdf')

            # Get the total number of pages
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(pdf_document)
            pdf_document.close()

            # Initialize processing status in Firestore
            db.collection('pdf_processes').document(pdf_id).set({
                'status': 'processing',
                'current_page': 0,
                'total_pages': total_pages,
                'summary': '',
                'processing_start_time': time.time(),
                'timestamp': firestore.SERVER_TIMESTAMP,
                'file_size': file_size
            })

            return jsonify({
                'pdf_id': pdf_id,
                'total_pages': total_pages,
                'file_size': file_size
            }), 200
        except Exception as e:
            logging.error(f"Error uploading file: {e}")
            return jsonify({'error': f'Error uploading file: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400

# Update the process_pdf_endpoint function
@app.route('/process_pdf', methods=['POST'])
def process_pdf_endpoint():
    data = request.get_json()
    pdf_id = data.get('pdf_id')
    if not pdf_id:
        logger.error("No PDF ID provided")
        return jsonify({'error': 'No PDF ID provided.'}), 400

    doc_ref = db.collection('pdf_processes').document(pdf_id)
    doc = doc_ref.get()
    if not doc.exists:
        logger.error(f"Invalid PDF ID: {pdf_id}")
        return jsonify({'error': 'Invalid PDF ID.'}), 400
    
    result = doc.to_dict()
    current_page = result['current_page']
    total_pages = result['total_pages']

    if current_page >= total_pages:
        logger.info(f"PDF {pdf_id} processing already completed")
        return jsonify({'status': 'completed'}), 200

    try:
        logger.info(f"Processing PDF {pdf_id}, page {current_page + 1} of {total_pages}")
        blob = bucket.blob(f'pdfs/{pdf_id}.pdf')
        pdf_bytes = blob.download_as_bytes()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

        process_page(pdf_document, current_page, doc_ref)
        pdf_document.close()

        updated_doc = doc_ref.get().to_dict()
        if updated_doc['current_page'] >= total_pages:
            logger.info(f"PDF {pdf_id} processing completed")
            doc_ref.update({
                'status': 'completed',
                'processing_end_time': time.time()
            })
            blob.delete()
            return jsonify({'status': 'completed'}), 200
        else:
            logger.info(f"PDF {pdf_id} processing in progress. Current page: {updated_doc['current_page']}")
            return jsonify({
                'status': 'processing',
                'current_page': updated_doc['current_page'],
                'total_pages': total_pages
            }), 200

    except Exception as e:
        logger.error(f"Error processing PDF {pdf_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/check_status', methods=['GET'])
def check_status():
    pdf_id = request.args.get('pdf_id')
    if not pdf_id:
        logger.error("No PDF ID provided for status check")
        return jsonify({'error': 'No PDF ID provided.'}), 400

    doc_ref = db.collection('pdf_processes').document(pdf_id)
    doc = doc_ref.get()
    if not doc.exists:
        logger.error(f"Invalid PDF ID for status check: {pdf_id}")
        return jsonify({'error': 'Invalid PDF ID.'}), 400
    
    result = doc.to_dict()
    status = result.get('status', 'processing')

    if status == 'completed':
        logger.info(f"Status check: PDF {pdf_id} processing completed")
        summary = '\n\n'.join(result['summary'])
        docx_buffer = create_word_document(summary)
        docx_base64 = base64.b64encode(docx_buffer.getvalue()).decode('utf-8')

        processing_time = 'N/A'
        if result.get('processing_start_time') and result.get('processing_end_time'):
            processing_time = int(result['processing_end_time'] - result['processing_start_time'])

        return jsonify({
            'status': 'completed',
            'docx': docx_base64,
            'total_pages': result.get('total_pages', 0),
            'processing_time': processing_time
        }), 200
    else:
        logger.info(f"Status check: PDF {pdf_id} processing in progress. Current page: {result.get('current_page', 0)}")
        return jsonify({
            'status': 'processing',
            'current_page': result.get('current_page', 0),
            'total_pages': result.get('total_pages', 0)
        }), 200
if __name__ == '__main__':
    app.run(debug=True)
