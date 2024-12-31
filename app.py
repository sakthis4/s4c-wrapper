from flask import Flask, jsonify, request
import os
from functools import wraps
from auth import APIKeyManager
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)
api_key_manager = APIKeyManager()

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

def fetch_instructor_led_training(subdomain, api_key, username, course_customfield):
    """
    Fetch 'Instructor-led training' units for a user in a course based on username and course custom field.
    Stops execution and returns appropriate messages if the username, course_customfield, or API key is invalid.
    
    :param subdomain: TalentLMS subdomain
    :param api_key: TalentLMS API key
    :param username: Username of the user
    :param course_customfield: Custom field value of the course
    :return: List of units with type 'Instructor-led training' or error message
    """
    try:
        # Validate API Key and User Details
        user_url = f"https://{subdomain}.talentlms.com/api/v1/users/username:{username}"
        user_response = requests.get(user_url, auth=HTTPBasicAuth(api_key, ''))

        if user_response.status_code == 401:
            return "Invalid API Key. Please provide a valid API Key."
        if user_response.status_code == 404:
            return f"User with username '{username}' not found."
        if user_response.status_code != 200:
            return f"Error fetching user details: {user_response.status_code}, {user_response.text}"

        user_data = user_response.json()
        user_id = user_data.get('id')

        if not user_id:
            return "User ID not found for the provided username."

        # Validate Course Details
        course_url = f"https://{subdomain}.talentlms.com/api/v1/getcoursesbycustomfield/custom_field_value:{course_customfield}"
        course_response = requests.get(course_url, auth=HTTPBasicAuth(api_key, ''))

        if course_response.status_code == 404:
            return f"Course with custom field value '{course_customfield}' not found."
        if course_response.status_code != 200:
            return f"Error fetching course details: {course_response.status_code}, {course_response.text}"

        courses = course_response.json()
        if not courses:
            return f"No courses found for the custom field value '{course_customfield}'."

        # Assuming the first course is the one we want
        course_id = courses[0].get('id')

        if not course_id:
            return "Course ID not found for the provided custom field value."

        # Get user status in course
        status_url = f"https://{subdomain}.talentlms.com/api/v1/getuserstatusincourse"
        status_params = {'user_id': user_id, 'course_id': course_id}
        status_response = requests.get(status_url, params=status_params, auth=HTTPBasicAuth(api_key, ''))

        if status_response.status_code != 200:
            return f"Error fetching user status in course: {status_response.status_code}, {status_response.text}"

        status_data = status_response.json()
        instructor_led_units = [
            unit for unit in status_data.get('units', [])
            if unit.get('type') == 'Instructor-led training'
        ]

        return instructor_led_units if instructor_led_units else "No 'Instructor-led training' units found."

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
                    'subdomain',
                    'talent_api_key',
                    'username',
                    'course_customfield'
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
@require_api_key
def get_data():
    # Get and validate required parameters
    subdomain = request.args.get('subdomain')
    talent_api_key = request.args.get('talent_api_key')
    username = request.args.get('username')
    course_customfield = request.args.get('course_customfield')
    
    # Validate required parameters
    if not all([subdomain, talent_api_key, username, course_customfield]):
        return jsonify({
            'error': 'Missing required parameters',
            'required_parameters': {
                'subdomain': 'TalentLMS subdomain',
                'talent_api_key': 'TalentLMS API key',
                'username': 'Username to check',
                'course_customfield': 'Course custom field value'
            }
        }), 400
    
    # Get customer_id for logging/tracking
    api_key = request.headers.get('X-API-Key')
    customer_id = api_key_manager.get_customer_id(api_key)
    
    # Fetch instructor-led training data
    training_data = fetch_instructor_led_training(
        subdomain=subdomain,
        api_key=talent_api_key,
        username=username,
        course_customfield=course_customfield
    )
    
    # Prepare response
    response = {
        'customer_id': customer_id,
        'request_parameters': {
            'subdomain': subdomain,
            'username': username,
            'course_customfield': course_customfield
        },
        'result': training_data
    }
    
    # If training_data is an error message (string), return as error
    if isinstance(training_data, str):
        return jsonify({'error': training_data}), 400
    
    return jsonify(response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)