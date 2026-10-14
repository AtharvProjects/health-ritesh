from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *
from app_v2.utils.services import *

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return render_template('index.html', msg='Logged out successfully')

@auth_bp.route('/AdminLogin', methods=['GET', 'POST'])
def AdminLogin():
    if request.method == 'GET':
        return render_template('AdminLogin.html', msg='')

@auth_bp.route('/AdminLoginAction', methods=['POST'])
def AdminLoginAction():
    if request.method == 'POST':
        username = request.form['t1']
        password = request.form['t2']
        password_hash = hashPassword(password)
        web3, contract, account = getContract()
        admin_count = contract.functions.adminCount().call()
        if admin_count == 0 and username == 'admin' and (password == 'admin'):
            data = username + '#' + password_hash
            saveDataBlockChain(data, 'admin')
            session['role'] = 'admin'
            session['user_id'] = 0
            session['username'] = username
            return render_template('AdminScreen.html', msg='Welcome ' + username)
        status, user_id = checkLogin(username, password, 'admin')
        if status == 'success':
            session['role'] = 'admin'
            session['user_id'] = user_id
            session['username'] = username
            return render_template('AdminScreen.html', msg='Welcome ' + username)
        return render_template('AdminLogin.html', msg='Invalid username or password')

@auth_bp.route('/PatientRegister', methods=['GET'])
def PatientRegister():
    return render_template('PatientRegister.html', msg='')

@auth_bp.route('/PatientRegisterAction', methods=['POST'])
def PatientRegisterAction():
    if request.method == 'POST':
        name = request.form['t1']
        gender = request.form['t2']
        dob = request.form['t3']
        contact = request.form['t4']
        address = request.form['t5']
        username = request.form['t6']
        password = hashPassword(request.form['t7'])
        readDetails('patient')
        arr = AppState.details.split('\n')
        for i in range(len(arr) - 1):
            row = arr[i].split('#')
            if row[6] == username:
                return render_template('PatientRegister.html', msg='Username already exists')
        data = name + '#' + gender + '#' + dob + '#' + contact + '#' + address + '#' + username + '#' + password
        saveDataBlockChain(data, 'patient')
        web3, contract, account = getContract()
        patient_id = contract.functions.patientCount().call() - 1
        return render_template('PatientRegister.html', msg='Registration successful. Login with username: ' + username + ' and your password. Patient ID: ' + formatId('patient', patient_id))

@auth_bp.route('/PatientLogin', methods=['GET'])
def PatientLogin():
    return render_template('PatientLogin.html', msg='')

@auth_bp.route('/PatientLoginAction', methods=['POST'])
def PatientLoginAction():
    if request.method == 'POST':
        username = request.form['t1']
        password = request.form['t2']
        if isFormattedId(username):
            return render_template('PatientLogin.html', msg='Please login with username and password, not Patient ID')
        status, user_id = checkLogin(username, password, 'patient')
        if status == 'success':
            session['role'] = 'patient'
            session['user_id'] = user_id
            session['username'] = username
            return render_template('PatientScreen.html', msg='Welcome, ' + username)
        return render_template('PatientLogin.html', msg='Invalid username or password')

@auth_bp.route('/DoctorLogin', methods=['GET'])
def DoctorLogin():
    return render_template('DoctorLogin.html', msg='')

@auth_bp.route('/DoctorLoginAction', methods=['POST'])
def DoctorLoginAction():
    if request.method == 'POST':
        username = request.form['t1']
        password = request.form['t2']
        if isFormattedId(username):
            return render_template('DoctorLogin.html', msg='Please login with username and password, not Doctor ID')
        status, user_id = checkLogin(username, password, 'doctor')
        if status == 'success':
            session['role'] = 'doctor'
            session['user_id'] = user_id
            session['username'] = username
            return render_template('DoctorScreen.html', msg='Welcome, ' + username)
        return render_template('DoctorLogin.html', msg='Invalid username or password')