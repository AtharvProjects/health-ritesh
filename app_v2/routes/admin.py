from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *
from app_v2.utils.services import *

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/AdminScreen', methods=['GET'])
def AdminScreen():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    return render_template('AdminScreen.html', msg='Admin Dashboard')

@admin_bp.route('/CreateOrganization', methods=['GET'])
def CreateOrganization():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    return render_template('CreateOrganization.html', msg='')

@admin_bp.route('/CreateOrganizationAction', methods=['POST'])
def CreateOrganizationAction():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    if request.method == 'POST':
        name = request.form['t1']
        address = request.form['t2']
        contact = request.form['t3']
        data = name + '#' + address + '#' + contact
        saveDataBlockChain(data, 'organization')
        web3, contract, account = getContract()
        org_id = contract.functions.organizationCount().call() - 1
        return render_template('CreateOrganization.html', msg='Organization saved to blockchain. Organization ID: ' + formatId('organization', org_id))

@admin_bp.route('/RegisterDoctor', methods=['GET'])
def RegisterDoctor():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    readDetails('organization')
    org_options = ''
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        org_options += "<option value='" + row[0] + "'>" + formatId('organization', row[0]) + ' - ' + row[1] + '</option>'
    return render_template('RegisterDoctor.html', msg='', options=org_options)

@admin_bp.route('/RegisterDoctorAction', methods=['POST'])
def RegisterDoctorAction():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    if request.method == 'POST':
        name = request.form['t1']
        spec = request.form['t2']
        org_id = request.form['t3']
        username = request.form['t4']
        password = hashPassword(request.form['t5'])
        readDetails('doctor')
        arr = AppState.details.split('\n')
        for i in range(len(arr) - 1):
            row = arr[i].split('#')
            if row[4] == username:
                readDetails('organization')
                org_options = ''
                org_arr = AppState.details.split('\n')
                for j in range(len(org_arr) - 1):
                    org_row = org_arr[j].split('#')
                    org_options += "<option value='" + org_row[0] + "'>" + formatId('organization', org_row[0]) + ' - ' + org_row[1] + '</option>'
                return render_template('RegisterDoctor.html', msg='Username already exists', options=org_options)
        data = name + '#' + spec + '#' + org_id + '#' + username + '#' + password
        saveDataBlockChain(data, 'doctor')
        web3, contract, account = getContract()
        doctor_id = contract.functions.doctorCount().call() - 1
        return render_template('RegisterDoctor.html', msg='Doctor registered successfully. Login with username: ' + username + ' and password. Doctor ID: ' + formatId('doctor', doctor_id), options='')

@admin_bp.route('/ViewOrganizations', methods=['GET'])
def ViewOrganizations():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Org ID', 'Name', 'Address', 'Contact']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    readDetails('organization')
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        output += '<tr><td>' + formatId('organization', row[0]) + '</td>'
        output += '<td>' + row[1] + '</td>'
        output += '<td>' + row[2] + '</td>'
        output += '<td>' + row[3] + '</td></tr>'
    output += '</table>'
    return render_template('ViewOrganizations.html', msg=output)

@admin_bp.route('/ViewDoctors', methods=['GET'])
def ViewDoctors():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Doctor ID', 'Name', 'Specialization', 'Organization ID', 'Username']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    readDetails('doctor')
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        output += '<tr><td>' + formatId('doctor', row[0]) + '</td>'
        output += '<td>' + row[1] + '</td>'
        output += '<td>' + row[2] + '</td>'
        output += '<td>' + formatId('organization', row[3]) + '</td>'
        output += '<td>' + row[4] + '</td></tr>'
    output += '</table>'
    return render_template('ViewDoctors.html', msg=output)

@admin_bp.route('/ViewPatients', methods=['GET'])
def ViewPatients():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Patient ID', 'Name', 'Gender', 'DOB', 'Contact', 'Address', 'Username']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    readDetails('patient')
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        output += '<tr><td>' + formatId('patient', row[0]) + '</td>'
        output += '<td>' + row[1] + '</td>'
        output += '<td>' + row[2] + '</td>'
        output += '<td>' + row[3] + '</td>'
        output += '<td>' + row[4] + '</td>'
        output += '<td>' + row[5] + '</td>'
        output += '<td>' + row[6] + '</td></tr>'
    output += '</table>'
    return render_template('ViewPatients.html', msg=output)

@admin_bp.route('/AuditLogs', methods=['GET'])
def AuditLogs():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    patient_names = {}
    doctor_names = {}
    org_names = {}
    readDetails('patient')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        patient_names[parts[0]] = parts[1]
    readDetails('doctor')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        doctor_names[parts[0]] = parts[1]
    readDetails('organization')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        org_names[parts[0]] = parts[1]
    output = "<h4 class='mt-2'>Organization Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Org ID</th><th>Name</th><th>Address</th><th>Contact</th></tr>'
    readDetails('organization')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        output += '<tr><td>' + formatId('organization', parts[0]) + '</td><td>' + parts[1] + '</td><td>' + parts[2] + '</td><td>' + parts[3] + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Doctor Registration Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Doctor ID</th><th>Name</th><th>Organization</th><th>Username</th></tr>'
    readDetails('doctor')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        org_name = org_names.get(parts[3], parts[3])
        output += '<tr><td>' + formatId('doctor', parts[0]) + '</td><td>' + parts[1] + '</td><td>' + org_name + ' (' + formatId('organization', parts[3]) + ')</td><td>' + parts[4] + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Patient Registration Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Patient ID</th><th>Name</th><th>Username</th></tr>'
    readDetails('patient')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        output += '<tr><td>' + formatId('patient', parts[0]) + '</td><td>' + parts[1] + '</td><td>' + parts[6] + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Medical Record Upload Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Record ID</th><th>Patient</th><th>IPFS Hash</th><th>Type</th><th>File Name</th></tr>'
    readDetails('record')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        patient_name = patient_names.get(parts[1], parts[1])
        file_name = parts[6] if len(parts) > 6 else ''
        output += '<tr><td>' + formatId('record', parts[0]) + '</td><td>' + patient_name + ' (' + formatId('patient', parts[1]) + ')</td><td>' + parts[2] + '</td><td>' + parts[3] + '</td><td>' + file_name + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Record Sharing Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Sharing ID</th><th>Record ID</th><th>Patient</th><th>Organization</th><th>Shared At</th></tr>'
    readDetails('sharing')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        patient_name = patient_names.get(parts[2], parts[2])
        org_name = org_names.get(parts[3], parts[3])
        output += '<tr><td>' + formatId('sharing', parts[0]) + '</td><td>' + formatId('record', parts[1]) + '</td><td>' + patient_name + ' (' + formatId('patient', parts[2]) + ')</td><td>' + org_name + ' (' + formatId('organization', parts[3]) + ')</td><td>' + formatLocalTime(parts[4]) + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Prescription Submission Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Prescription ID</th><th>Patient</th><th>Doctor</th><th>Record ID</th><th>Submitted At</th><th>Status</th></tr>'
    readDetails('prescription')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        patient_name = patient_names.get(parts[1], parts[1])
        doctor_name = doctor_names.get(parts[2], parts[2])
        output += '<tr><td>' + formatId('prescription', parts[0]) + '</td><td>' + patient_name + ' (' + formatId('patient', parts[1]) + ')</td><td>' + doctor_name + ' (' + formatId('doctor', parts[2]) + ')</td><td>' + formatId('record', parts[3]) + '</td><td>' + formatLocalTime(parts[6]) + '</td><td>' + parts[7] + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Record Access Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Access ID</th><th>Doctor</th><th>Record ID</th><th>Patient</th><th>Organization</th><th>Accessed At</th></tr>'
    readDetails('access')
    for row in AppState.details.split('\n')[:-1]:
        parts = row.split('#')
        doctor_name = doctor_names.get(parts[1], parts[1])
        patient_name = patient_names.get(parts[3], parts[3])
        org_name = org_names.get(parts[4], parts[4])
        output += '<tr><td>' + formatId('access', parts[0]) + '</td><td>' + doctor_name + ' (' + formatId('doctor', parts[1]) + ')</td><td>' + formatId('record', parts[2]) + '</td><td>' + patient_name + ' (' + formatId('patient', parts[3]) + ')</td><td>' + org_name + ' (' + formatId('organization', parts[4]) + ')</td><td>' + formatLocalTime(parts[5]) + '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Prescription View Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Prescription ID</th><th>Viewer</th><th>Patient</th><th>Doctor</th><th>Record ID</th></tr>'
    view_logs = getPrescriptionViewLogs()
    if len(view_logs) == 0:
        output += "<tr><td colspan='5'>No prescription view logs yet</td></tr>"
    for log in view_logs:
        output += '<tr><td>' + log['prescription_id'] + '</td><td>' + log['viewer_name'] + ' (' + log['viewer_id'] + ')</td><td>' + log['patient_name'] + '</td><td>' + log['doctor_name'] + '</td><td>' + log['record_id'] + '</td></tr>'
    output += '</table>'
    return render_template('AuditLogs.html', msg=output)

@admin_bp.route('/Analytics', methods=['GET'])
def Analytics():
    err = mustBeRole('admin', 'AdminLogin.html')
    if err:
        return err
    readDetails('analytics')
    row = AppState.details.split('#')
    labels = ['Organizations', 'Doctors', 'Patients', 'Records', 'Sharings', 'Prescriptions', 'Access Logs']
    values = [int(row[i]) for i in range(7)]
    output = "<h4>Summary</h4><table class='" + TABLE_CLASS + "'>"
    output += '<tr><th>Metric</th><th>Count</th></tr>'
    for i in range(len(labels)):
        output += '<tr><td>' + labels[i] + '</td><td>' + str(values[i]) + '</td></tr>'
    avg_encrypt = float(row[7]) if row[7] else 0
    avg_decrypt = float(row[8]) if row[8] else 0
    time_diff = round(abs(avg_encrypt - avg_decrypt), 2)
    if avg_encrypt > avg_decrypt:
        time_compare = 'Encryption is slower than decryption by ' + str(time_diff) + ' ms'
    elif avg_decrypt > avg_encrypt:
        time_compare = 'Decryption is slower than encryption by ' + str(time_diff) + ' ms'
    else:
        time_compare = 'Encryption and decryption times are equal'
    output += '<tr><td>Blockchain Transactions (session)</td><td>' + row[9] + '</td></tr>'
    output += '</table>'
    org_names = {}
    readDetails('organization')
    for org_row in AppState.details.split('\n')[:-1]:
        parts = org_row.split('#')
        org_names[parts[0]] = parts[1]
    _, contract, _ = getContract()
    org_share_labels = []
    org_share_values = []
    readDetails('record')
    record_arr = AppState.details.split('\n')[:-1]
    for org_id in sorted(org_names.keys()):
        active_count = 0
        for rec in record_arr:
            rec_parts = rec.split('#')
            if contract.functions.isRecordSharedWithOrg(int(rec_parts[0]), int(org_id)).call():
                active_count += 1
        if active_count > 0:
            org_share_labels.append(org_names[org_id])
            org_share_values.append(active_count)
    doctor_names = {}
    readDetails('doctor')
    for doc_row in AppState.details.split('\n')[:-1]:
        parts = doc_row.split('#')
        doctor_names[parts[0]] = parts[1]
    doctor_pres_labels = []
    doctor_pres_values = []
    readDetails('prescription')
    doctor_pres_count = {}
    for pres_row in AppState.details.split('\n')[:-1]:
        parts = pres_row.split('#')
        doctor_id = parts[2]
        if doctor_id not in doctor_pres_count:
            doctor_pres_count[doctor_id] = 0
        doctor_pres_count[doctor_id] += 1
    for doctor_id in sorted(doctor_pres_count.keys()):
        doctor_pres_labels.append(doctor_names.get(doctor_id, 'Doctor ' + doctor_id))
        doctor_pres_values.append(doctor_pres_count[doctor_id])
    chart_summary = json.dumps({'labels': labels, 'values': values})
    chart_share = json.dumps({'labels': org_share_labels, 'values': org_share_values})
    chart_doctor = json.dumps({'labels': doctor_pres_labels, 'values': doctor_pres_values})
    run_labels = [f'Run {i + 1}' for i in range(max(len(AppState.encryption_times), len(AppState.decryption_times)))]
    chart_encrypt = json.dumps({'labels': run_labels, 'encryption': AppState.encryption_times, 'decryption': AppState.decryption_times})
    return render_template('Analytics.html', msg=output, chart_summary=chart_summary, chart_share=chart_share, chart_doctor=chart_doctor, chart_encrypt=chart_encrypt)