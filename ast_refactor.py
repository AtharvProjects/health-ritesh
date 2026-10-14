import ast
import os

with open('app.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())

route_groups = {
    'auth': ['/logout', '/PatientLogin', '/PatientLoginAction', '/DoctorLogin', '/DoctorLoginAction', '/AdminLogin', '/AdminLoginAction', '/PatientRegister', '/PatientRegisterAction'],
    'admin': ['/AdminScreen', '/CreateOrganization', '/CreateOrganizationAction', '/RegisterDoctor', '/RegisterDoctorAction', '/ViewOrganizations', '/ViewDoctors', '/ViewPatients', '/AuditLogs', '/Analytics'],
    'patient': ['/PatientScreen', '/UploadRecord', '/UploadRecordAction', '/ViewMyRecords', '/ManageRecordSharing/<record_id>', '/ShareRecordAction', '/RevokeShareAction', '/ViewPatientPrescription'],
    'doctor': ['/DoctorScreen', '/ViewSharedRecords', '/ViewPatientHistory', '/SubmitPrescription/<record_id>/<patient_id>', '/SubmitPrescriptionAction', '/ViewDoctorPrescription'],
    'main': ['/', '/DownloadRecord/<record_id>', '/DownloadPrescription/<prescription_id>']
}

routes_code = {k: [] for k in route_groups.keys()}
services_code = []

# Known functions already in utils
known_utils = ['hashPassword', 'formatLocalTime', 'formatId', 'parseId', 'isFormattedId', 'isLegacyRecord', 'mustBeRole', 'escapeHtml', 'isTextContent', 'loadOrCreateKeys', 'aesEncrypt', 'aesDecrypt', 'paillierEncrypt', 'paillierDecrypt', 'doubleEncrypt', 'doubleDecrypt', 'uploadToPinata', 'downloadFromIpfs', 'decryptFromIpfs', 'getDecryptedFileBytes', 'safeGetDecryptedFileBytes', 'getContract', 'readDetails', 'saveDataBlockChain']

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        is_route = False
        route_path = ''
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') == 'route':
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    route_path = dec.args[0].value
                    is_route = True
        
        if is_route:
            assigned_group = 'main'
            for group, paths in route_groups.items():
                if route_path in paths:
                    assigned_group = group
                    break
            
            # modify decorator
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') == 'route':
                    dec.func.value.id = f'{assigned_group}_bp'
            
            routes_code[assigned_group].append(ast.unparse(node))
        else:
            if node.name not in known_utils:
                services_code.append(ast.unparse(node))

os.makedirs('app_v2/routes', exist_ok=True)
os.makedirs('app_v2/utils', exist_ok=True)

for group, code_blocks in routes_code.items():
    header = f"""from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *
from app_v2.utils.services import *

{group}_bp = Blueprint('{group}', __name__)
"""
    with open(f'app_v2/routes/{group}.py', 'w', encoding='utf-8') as f:
        f.write(header + '\n\n' + '\n\n'.join(code_blocks))

services_header = """from flask import render_template, session
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *

"""
with open('app_v2/utils/services.py', 'w', encoding='utf-8') as f:
    f.write(services_header + '\n\n'.join(services_code))

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

print("AST Parsing complete!")
