import os
import re

app_path = 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make routes directory
os.makedirs('app_v2/routes', exist_ok=True)

# 1. Extract everything between `loadOrCreateKeys()` and `app = Flask(__name__)`
# No, we want to extract functions and routes.

# Define the route groupings
route_groups = {
    'auth': ['/logout', '/PatientLogin', '/PatientLoginAction', '/DoctorLogin', '/DoctorLoginAction', '/AdminLogin', '/AdminLoginAction', '/PatientRegister', '/PatientRegisterAction'],
    'admin': ['/AdminScreen', '/CreateOrganization', '/CreateOrganizationAction', '/RegisterDoctor', '/RegisterDoctorAction', '/ViewOrganizations', '/ViewDoctors', '/ViewPatients', '/AuditLogs', '/Analytics'],
    'patient': ['/PatientScreen', '/UploadRecord', '/UploadRecordAction', '/ViewMyRecords', '/ManageRecordSharing/<record_id>', '/ShareRecordAction', '/RevokeShareAction', '/ViewPatientPrescription'],
    'doctor': ['/DoctorScreen', '/ViewSharedRecords', '/ViewPatientHistory', '/SubmitPrescription/<record_id>/<patient_id>', '/SubmitPrescriptionAction', '/ViewDoctorPrescription'],
    'main': ['/', '/DownloadRecord/<record_id>', '/DownloadPrescription/<prescription_id>']
}

# The goal is to create a robust factory app instead of regexing python code which might fail.
# Since we are creating a V2 app, let's write a simple script that creates the core Blueprints setup.
# Actually, I will write the Blueprints manually via this script.

blueprint_template = """from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *

{name}_bp = Blueprint('{name}', __name__)
"""

# Instead of complex regex, let's copy the whole monolith logic into `routes/monolith.py` for now, 
# but register it as a blueprint. Wait, the user wants it modularized. 
# Writing a regex to extract `@app.route` and its following function:
functions = {}
current_func = []
func_name = None

lines = content.split('\n')
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('@app.route'):
        # Extract route path
        route_path = re.search(r'@app\.route\("([^"]+)"', line)
        if not route_path:
            route_path = re.search(r"@app\.route\('([^']+)'", line)
        path = route_path.group(1) if route_path else line
        
        # Read the decorator and function
        func_lines = [line]
        i += 1
        while i < len(lines) and (lines[i].startswith(' ') or lines[i].startswith('\t') or lines[i].startswith('def ') or lines[i].startswith('@') or lines[i].strip() == ''):
            if lines[i].startswith('def '):
                name_match = re.search(r'def ([a-zA-Z0-9_]+)\(', lines[i])
                if name_match:
                    func_name = name_match.group(1)
            func_lines.append(lines[i])
            i += 1
        
        # Replace @app.route with @bp.route
        functions[path] = '\n'.join(func_lines)
        continue
    i += 1

# Write routes
for group, paths in route_groups.items():
    code = blueprint_template.format(name=group)
    for p in paths:
        if p in functions:
            func_code = functions[p].replace('@app.route', f'@{group}_bp.route')
            code += '\n' + func_code + '\n'
    
    with open(f'app_v2/routes/{group}.py', 'w', encoding='utf-8') as f:
        f.write(code)

# Extract non-route helper functions
helpers_code = ""
in_helper = False
for line in lines:
    if line.startswith('def '):
        name_match = re.search(r'def ([a-zA-Z0-9_]+)\(', line)
        if name_match:
            name = name_match.group(1)
            # if it's a known route function or already in utils, skip
            is_route = False
            for group, paths in route_groups.items():
                for p in paths:
                    if p in functions and f'def {name}(' in functions[p]:
                        is_route = True
            
            # Known utils
            known_utils = ['hashPassword', 'formatLocalTime', 'formatId', 'parseId', 'isFormattedId', 'isLegacyRecord', 'mustBeRole', 'escapeHtml', 'isTextContent', 'loadOrCreateKeys', 'aesEncrypt', 'aesDecrypt', 'paillierEncrypt', 'paillierDecrypt', 'doubleEncrypt', 'doubleDecrypt', 'uploadToPinata', 'downloadFromIpfs', 'decryptFromIpfs', 'getDecryptedFileBytes', 'safeGetDecryptedFileBytes', 'getContract', 'readDetails', 'saveDataBlockChain']
            
            if not is_route and name not in known_utils:
                in_helper = True
                helpers_code += line + "\n"
            else:
                in_helper = False
    elif in_helper:
        if line.startswith('@app.route'):
            in_helper = False
        else:
            helpers_code += line + "\n"

with open('app_v2/utils/services.py', 'w', encoding='utf-8') as f:
    f.write("from app_v2.config import Config, AppState\n")
    f.write("from app_v2.utils.helpers import *\n")
    f.write("from app_v2.utils.blockchain import *\n")
    f.write("from app_v2.utils.crypto import *\n")
    f.write("from app_v2.utils.ipfs import *\n")
    f.write("from flask import render_template, session\n\n")
    f.write(helpers_code)

# Write app factory
factory_code = """from flask import Flask
from app_v2.config import Config
from app_v2.utils.crypto import loadOrCreateKeys
from app_v2.routes.auth import auth_bp
from app_v2.routes.admin import admin_bp
from app_v2.routes.patient import patient_bp
from app_v2.routes.doctor import doctor_bp
from app_v2.routes.main import main_bp

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = Config.SECRET_KEY
    
    # Load keys
    loadOrCreateKeys()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(main_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
"""
with open('app_v2/run.py', 'w', encoding='utf-8') as f:
    f.write(factory_code)

print("Routes successfully modularized!")
