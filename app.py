from flask import Flask, jsonify, request
import os
from functools import wraps
from auth import APIKeyManager
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
api_key_manager = APIKeyManager()

# Get environment variables
TALENT_SUBDOMAIN = os.getenv('TALENT_SUBDOMAIN')
TALENT_API_KEY = os.getenv('TALENT_API_KEY')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'No API key provided'}), 401
        
        if not api_key_manager.verify_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def fetch_instructor_led_training(student_id, batch_id, subdomain=TALENT_SUBDOMAIN, api_key=TALENT_API_KEY):
    """
    Fetch 'Instructor-led training' units for a user in a course based on student_id and batch_id.
    Stops execution and returns appropriate messages if the student_id, batch_id, or API key is invalid.
    
    :param subdomain: TalentLMS subdomain
    :param api_key: TalentLMS API key
    :param student_id: Student ID of the user
    :param batch_id: Batch ID value of the course
    :return: List of units with type 'Instructor-led training' or error message
    """
    try:
        # Validate API Key and User Details
        user_url = f"https://{subdomain}.talentlms.com/api/v1/users/username:{student_id}"
        user_response = requests.get(user_url, auth=HTTPBasicAuth(api_key, ''))

        if user_response.status_code == 401:
            return "Invalid API Key. Please provide a valid API Key."
        if user_response.status_code == 404:
            return f"User with student_id '{student_id}' not found."
        if user_response.status_code != 200:
            return f"Error fetching user details: {user_response.status_code}, {user_response.text}"

        user_data = user_response.json()
        user_id = user_data.get('id')

        if not user_id:
            return "User ID not found for the provided student_id."

        # Validate Course Details
        course_url = f"https://{subdomain}.talentlms.com/api/v1/getcoursesbycustomfield/custom_field_value:{batch_id}"
        course_response = requests.get(course_url, auth=HTTPBasicAuth(api_key, ''))

        if course_response.status_code == 404:
            return f"Course with batch ID '{batch_id}' not found."
        if course_response.status_code != 200:
            return f"Error fetching course details: {course_response.status_code}, {course_response.text}"

        courses = course_response.json()
        if not courses:
            return f"No courses found for the batch ID '{batch_id}'."

        # Assuming the first course is the one we want
        course_id = courses[0].get('id')

        if not course_id:
            return "Course ID not found for the provided batch ID."

        # Get user status in course
        status_url = f"https://{subdomain}.talentlms.com/api/v1/getuserstatusincourse"
        status_params = {'user_id': user_id, 'course_id': course_id}
        status_response = requests.get(status_url, params=status_params, auth=HTTPBasicAuth(api_key, ''))

        if status_response.status_code != 200:
            return f"Error fetching user status in course: {status_response.status_code}, {status_response.text}"

        status_data = status_response.json()
        instructor_led_units = [
            {
                'id': unit.get('id'),
                'name': unit.get('name')
            }
            for unit in status_data.get('units', [])
            if unit.get('type') == 'Instructor-led training'
        ]

        return instructor_led_units if instructor_led_units else "No 'Instructor-led training' units found."

    except requests.RequestException as e:
        return f"An error occurred: {str(e)}"

def get_ilt_sessions_by_id(subdomain, api_key, ilt_id):
    """
    Fetch Instructor-Led Training (ILT) sessions by ILT ID.
    """
    try:
        url = f"https://{subdomain}.talentlms.com/api/v1/getiltsessions"
        params = {'ilt_id': ilt_id}
        response = requests.get(url, params=params, auth=HTTPBasicAuth(api_key, ''))

        if response.status_code == 401:
            return "Invalid API Key. Please provide a valid API Key."
        if response.status_code == 404:
            return f"No ILT sessions found for ILT ID '{ilt_id}'."
        if response.status_code != 200:
            return f"Error fetching ILT sessions: {response.status_code}, {response.text}"

        sessions = response.json()
        if not sessions:
            return f"No sessions available for ILT ID '{ilt_id}'."

        # Extract only name and description from sessions
        simplified_sessions = [
            {
                'name': session.get('name'),
                'description': session.get('description')
            }
            for session in sessions
        ]
        
        return simplified_sessions

    except requests.RequestException as e:
        return f"An error occurred: {str(e)}"

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'Welcome to the API',
        'available_endpoints': {
            '/api/generate_key': {
                'method': 'GET',
                'params': ['customer_id']
            },
            '/api/data': {
                'method': 'GET',
                'headers': ['X-API-Key'],
                'params': [
                    'student_id',
                    'batch_id'
                ]
            }
        }
    })

@app.route('/api/generate_key', methods=['GET'])
def generate_key():
    customer_id = request.args.get('customer_id')
    
    if not customer_id:
        return jsonify({'error': 'customer_id is required as query parameter'}), 400
    
    api_key = api_key_manager.generate_api_key(customer_id)
    return jsonify({
        'customer_id': customer_id,
        'api_key': api_key
    })

@app.route('/api/data', methods=['GET'])
def get_data():
    # First validate API key
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'No API key provided'}), 401
    
    # Get and validate customer_id
    customer_id = api_key_manager.get_customer_id(api_key)
    if not customer_id:
        return jsonify({'error': 'Invalid API key'}), 401
    
    # Get required parameters
    student_id = request.args.get('student_id')
    batch_id = request.args.get('batch_id')
    
    # Validate required parameters
    if not all([student_id, batch_id]):
        return jsonify({
            'error': 'Missing required parameters',
            'required_parameters': {
                'student_id': 'Student ID to check',
                'batch_id': 'Batch ID value'
            }
        }), 400
    
    # Fetch instructor-led training data
    training_data = fetch_instructor_led_training(
        student_id=student_id,
        batch_id=batch_id
    )
    
    if isinstance(training_data, str):
        return jsonify({'error': training_data}), 400

    # Fetch ILT sessions for each training unit
    sessions_data = []
    for unit in training_data:
        ilt_sessions = get_ilt_sessions_by_id(
            subdomain=TALENT_SUBDOMAIN,
            api_key=TALENT_API_KEY,
            ilt_id=unit['id']
        )
        if not isinstance(ilt_sessions, str):  # if not an error message
            sessions_data.extend(ilt_sessions)
    
    # Prepare response
    response = {
        'customer_id': customer_id,
        'request_parameters': {
            'student_id': student_id,
            'batch_id': batch_id
        },
        'result': sessions_data if sessions_data else "No ILT sessions found"
    }
    
    return jsonify(response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)