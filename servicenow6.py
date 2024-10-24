from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import json

app = Flask(__name__)
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

# 1. Token megszerzése és háttéradatok lekérése egyben (jegy létrehozásnál)
@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    request_data = request.json
    username = request_data.get('username')
    password = request_data.get('password')
    short_description = request_data.get('short_description')

    auth_data = {
        'grant_type': 'password',
        'client_id': '45f3f2fb2ead4928ab994c64c664dfdc',
        'client_secret': 'fyHL1.@d&7',
        'username': username,
        'password': password
    }

    # 1. Token megszerzése
    response = requests.post('https://dev227667.service-now.com/oauth_token.do', data=auth_data)
    
    if response.status_code == 200:
        access_token = response.json().get('access_token')
        store_session_data(f'{username}_token', access_token)

        # 2. Felhasználói sys_id lekérése és mentése COS-ba
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

        # 3. Assignment groupok és prioritások lekérése
        response_groups = requests.get('https://dev227667.service-now.com/api/now/table/sys_user_group', headers=headers)
        if response_groups.status_code == 200:
            groups = [{"name": group["name"], "sys_id": group["sys_id"]} for group in response_groups.json().get('result', [])]
        else:
            return jsonify({"error": "Failed to fetch assignment groups"}), 400

        response_priorities = requests.get('https://dev227667.service-now.com/api/now/table/sys_choice?sysparm_query=name=incident^element=priority', headers=headers)
        if response_priorities.status_code == 200:
            priorities = [{"label": priority["label"], "value": priority["value"]} for priority in response_priorities.json().get('result', [])]
        else:
            return jsonify({"error": "Failed to fetch priorities"}), 400

        # 4. Válasszon csoportot és prioritást a felhasználó a lenyíló menüből
        assignment_group_sys_id = request_data.get('assignment_group_sys_id')  # lenyíló lista alapján kiválasztott
        priority = request_data.get('priority')  # lenyíló lista alapján kiválasztott

        # 5. Jegy létrehozása ServiceNow-ban
        current_caller_id = get_session_data(f'{username}_caller_id')
        if not current_caller_id:
            return jsonify({"error": "Caller ID not available. Please authenticate first."}), 400

        ticket_data = {
            "short_description": short_description,
            "assignment_group": assignment_group_sys_id,
            "priority": priority,
            "caller_id": current_caller_id
        }

        response_ticket = requests.post('https://dev227667.service-now.com/api/now/table/incident', json=ticket_data, headers=headers)

        if response_ticket.status_code == 201:
            return jsonify({"message": "Ticket created successfully", "ticket_number": response_ticket.json().get('result', {}).get('number')}), 201
        else:
            return jsonify({"error": "Failed to create ticket", "details": response_ticket.text}), 400

    else:
        return jsonify({"error": "Authentication failed", "details": response.text}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
