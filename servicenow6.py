from flask import Flask, request, jsonify
from flask_cors import CORS  # CORS importálása
import requests
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import json

app = Flask(__name__)

# CORS engedélyezése az alkalmazás minden végpontján
CORS(app)

# IBM Cloud Object Storage configuration
cos = ibm_boto3.client(
    's3',
    ibm_api_key_id='UZ0-SGtOYDF0aGrbKO9fAvBwy901L0xZqd7dJfWveV-2',
    ibm_service_instance_id='crn:v1:bluemix:public:cloud-object-storage:global:a/c9b79e3ae1594628bb4d214193b9cb75:e310fa1f-ff9f-443e-b3fd-c86719b7e9e6:bucket:elekteszt',
    config=Config(signature_version='oauth'),
    endpoint_url='https://s3.us-south.cloud-object-storage.appdomain.cloud'
)

# Helper function to store session data in IBM COS
def store_session_data(file_name, data):
    try:
        json_data = json.dumps(data)
        cos.put_object(Bucket='elekteszt', Key=file_name, Body=json_data)
    except ClientError as e:
        print(f"Error storing {file_name}: {e}")

# Helper function to retrieve session data from IBM COS
def get_session_data(file_name):
    try:
        response = cos.get_object(Bucket='elekteszt', Key=file_name)
        data = response['Body'].read().decode('utf-8')
        return json.loads(data)
    except ClientError as e:
        print(f"Error retrieving {file_name}: {e}")
        return None

# 1. Token megszerzése és háttéradatok lekérése
@app.route('/login', methods=['POST'])
def login():
    request_data = request.json
    username = request_data.get('username')
    password = request_data.get('password')

    auth_data = {
        'grant_type': 'password',
        'client_id': '45f3f2fb2ead4928ab994c64c664dfdc',
        'client_secret': 'fyHL1.@d&7',
        'username': username,
        'password': password
    }

    # Token megszerzése
    response = requests.post('https://dev227667.service-now.com/oauth_token.do', data=auth_data)
    
    if response.status_code == 200:
        access_token = response.json().get('access_token')
        store_session_data(f'{username}_token', access_token)

        # Felhasználói sys_id lekérése és mentése COS-ba
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        response_user = requests.get(
            f"https://dev227667.service-now.com/api/now/table/sys_user?sysparm_query=user_name={username}",
            headers=headers
        )
        if response_user.status_code == 200:
            users = response_user.json().get('result', [])
            if users:
                current_caller_id = users[0].get("sys_id")
                store_session_data(f'{username}_caller_id', current_caller_id)

        # Assignment groupok és prioritások lekérése
        response_groups = requests.get('https://dev227667.service-now.com/api/now/table/sys_user_group', headers=headers)
        if response_groups.status_code == 200:
            groups = [{"name": group["name"], "sys_id": group["sys_id"]} for group in response_groups.json().get('result', [])]
            store_session_data(f'{username}_assignment_groups', groups)

        response_priorities = requests.get('https://dev227667.service-now.com/api/now/table/sys_choice?sysparm_query=name=incident^element=priority', headers=headers)
        if response_priorities.status_code == 200:
            priorities = [{"label": priority["label"], "value": priority["value"]} for priority in response_priorities.json().get('result', [])]
            store_session_data(f'{username}_priorities', priorities)

        # Sikeres token megszerzés és adatlekérés után válaszolunk
        return jsonify({"message": "Data retrieved and token stored successfully", "username": username}), 200
    else:
        return jsonify({"error": "Authentication failed", "details": response.text}), 400

# 2. Assignment Group és Priority lekérése a jegy létrehozása előtt
@app.route('/get_ticket_data', methods=['GET'])
def get_ticket_data():
    username = request.args.get('username')

    assignment_groups = get_session_data(f'{username}_assignment_groups')
    priorities = get_session_data(f'{username}_priorities')

    if assignment_groups and priorities:
        return jsonify({
            "assignment_groups": assignment_groups,
            "priorities": priorities
        }), 200
    else:
        return jsonify({"error": "No data available"}), 404

# 3. Jegy létrehozása API kérés alapján
@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    request_data = request.json
    username = request_data.get('username')
    short_description = request_data.get('short_description')
    assignment_group_sys_id = request_data.get('assignment_group_sys_id')
    priority = request_data.get('priority')

    access_token = get_session_data(f'{username}_token')
    current_caller_id = get_session_data(f'{username}_caller_id')

    if not access_token or not current_caller_id:
        return jsonify({"error": "Token or Caller ID not available. Please authenticate first."}), 400

    # Jegy létrehozása ServiceNow-ban
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    ticket_data = {
        "short_description": short_description,
        "assignment_group": assignment_group_sys_id,
        "priority": priority,
        "caller_id": current_caller_id
    }

    response = requests.post('https://dev227667.service-now.com/api/now/table/incident', json=ticket_data, headers=headers)

    if response.status_code == 201:
        return jsonify({"message": "Ticket created successfully", "ticket_number": response.json().get('result', {}).get('number')}), 201
    else:
        return jsonify({"error": "Failed to create ticket", "details": response.text}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
