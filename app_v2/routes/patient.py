from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *
from app_v2.utils.services import *

patient_bp = Blueprint('patient', __name__)


@patient_bp.route('/PatientScreen', methods=['GET'])
def PatientScreen():
    err = mustBeRole('patient', 'PatientLogin.html')
    if err:
        return err
    username = session.get('username', '')
    msg = 'Patient Dashboard'
    if username != '':
        msg = 'Patient Dashboard | Logged in as: ' + username
    return render_template('PatientScreen.html', msg=msg)

@patient_bp.route('/UploadRecord', methods=['GET'])
def UploadRecord():
    if 'user_id' not in session or session.get('role') != 'patient':
        return render_template('UploadRecord.html', msg='Please login as patient first', username='', patient_id='', options='')
    patient_id = session['user_id']
    org_options = getOrganizationOptions()
    return render_template('UploadRecord.html', msg='', username=session.get('username', ''), patient_id=formatId('patient', patient_id), options=org_options)

@patient_bp.route('/UploadRecordAction', methods=['POST'])
def UploadRecordAction():
    if request.method == 'POST':
        patient_id = session.get('user_id', '')
        org_options = getOrganizationOptions()
        if session.get('role') != 'patient':
            return render_template('UploadRecord.html', msg='Please login as patient first', username=session.get('username', ''), patient_id=formatId('patient', patient_id) if patient_id != '' else '', options=org_options)
        record_type = request.form['t1']
        record_text = request.form.get('t3', '')
        file = request.files.get('t2')
        org_ids = request.form.getlist('t4')
        if file and file.filename:
            raw_data = file.read()
            original_filename = file.filename
        elif record_text.strip() != '':
            raw_data = record_text.encode('utf-8')
            original_filename = 'record_text.txt'
        else:
            return render_template('UploadRecord.html', msg='Please upload a file or enter text', username=session.get('username', ''), patient_id=formatId('patient', patient_id), options=org_options)
        if len(org_ids) == 0:
            return render_template('UploadRecord.html', msg='Please select at least one organization to share with', username=session.get('username', ''), patient_id=formatId('patient', patient_id), options=org_options)
        encrypted_data = doubleEncrypt(raw_data)
        ipfs_hash = uploadToPinata(encrypted_data, 'encrypted_record.b64')
        data = str(patient_id) + '#' + ipfs_hash + '#' + record_type + '#' + original_filename
        saveDataBlockChain(data, 'record')
        web3, contract, account = getContract()
        record_id = contract.functions.recordCount().call() - 1
        for org_id in org_ids:
            share_data = str(record_id) + '#' + str(patient_id) + '#' + org_id
            saveDataBlockChain(share_data, 'sharing')
        return render_template('UploadRecord.html', msg='Record uploaded successfully. Record ID: ' + formatId('record', record_id) + ' | Shared with selected organizations', username=session.get('username', ''), patient_id=formatId('patient', patient_id), options=org_options)

@patient_bp.route('/ViewMyRecords', methods=['GET'])
def ViewMyRecords():
    err = mustBeRole('patient', 'PatientLogin.html')
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Record ID', 'Patient ID', 'IPFS Hash', 'Record Type', 'Uploaded At', 'Shared With', 'Prescription Status', 'Content / Download', 'Manage Sharing']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    patient_id = str(session.get('user_id', ''))
    readDetails('record')
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        if row[1] == patient_id:
            hash_display = row[2]
            if isLegacyRecord(row[2]):
                hash_display = '[LEGACY] ' + row[2]
            _, lock_status = getRecordPrescriptionStatus(row[0])
            shared_orgs = getRecordSharedOrganizations(row[0])
            if len(shared_orgs) == 0:
                shared_text = 'None'
            else:
                shared_text = ', '.join([org['org_name'] for org in shared_orgs])
            output += '<tr><td>' + formatId('record', row[0]) + '</td>'
            output += '<td>' + formatId('patient', row[1]) + '</td>'
            output += '<td>' + hash_display + '</td>'
            output += '<td>' + row[3] + '</td>'
            output += '<td>' + formatLocalTime(row[4]) + '</td>'
            output += '<td>' + shared_text + '</td>'
            output += '<td>' + lock_status + '</td>'
            file_name = row[6] if len(row) > 6 else ''
            output += '<td>' + recordContentDownloadCell(row[0], row[2], file_name) + '</td>'
            output += "<td><a href='/ManageRecordSharing/" + formatId('record', row[0]) + "' class='btn btn-warning btn-sm'>Manage</a></td></tr>"
    output += '</table>'
    return render_template('ViewMyRecords.html', page_title='My Medical Records', status_msg='', msg=output)

@patient_bp.route('/ManageRecordSharing/<record_id>', methods=['GET'])
def ManageRecordSharing(record_id):
    err = mustBeRole('patient', 'PatientLogin.html')
    if err:
        return err
    patient_id = str(session.get('user_id', ''))
    _, contract, _ = getContract()
    record_id_int = parseId(record_id)
    record_patient_id = contract.functions.getRecordPatientId(record_id_int).call()
    if str(record_patient_id) != patient_id:
        return render_template('ViewMyRecords.html', page_title='My Medical Records', status_msg="<div class='alert alert-danger'>You are not allowed to manage this record</div>", msg='')
    return render_template('ViewMyRecords.html', page_title='Manage Record Sharing', status_msg='', msg=buildManageSharingPage(record_id_int, patient_id))

@patient_bp.route('/ShareRecordAction', methods=['POST'])
def ShareRecordAction():
    err = mustBeRole('patient', 'PatientLogin.html')
    if err:
        return err
    record_id = parseId(request.form['t1'])
    org_ids = request.form.getlist('t2')
    patient_id = str(session.get('user_id', ''))
    if len(org_ids) == 0:
        status_msg = 'Please select at least one organization'
        alert_class = 'alert-danger'
    else:
        for org_id in org_ids:
            share_data = str(record_id) + '#' + patient_id + '#' + org_id
            saveDataBlockChain(share_data, 'sharing')
        status_msg = 'Record shared with selected organizations successfully'
        alert_class = 'alert-info'
    return render_template('ViewMyRecords.html', page_title='Manage Record Sharing', status_msg="<div class='alert " + alert_class + "'>" + status_msg + '</div>', msg=buildManageSharingPage(record_id, patient_id))

@patient_bp.route('/RevokeShareAction', methods=['POST'])
def RevokeShareAction():
    err = mustBeRole('patient', 'PatientLogin.html')
    if err:
        return err
    record_id = parseId(request.form['t1'])
    org_id = request.form['t2']
    patient_id = str(session.get('user_id', ''))
    revoke_data = str(record_id) + '#' + patient_id + '#' + org_id
    saveDataBlockChain(revoke_data, 'revoke_share')
    return render_template('ViewMyRecords.html', page_title='Manage Record Sharing', status_msg="<div class='alert alert-info'>Sharing revoked successfully</div>", msg=buildManageSharingPage(record_id, patient_id))

@patient_bp.route('/ViewPatientPrescription', methods=['GET'])
def ViewPatientPrescription():
    err = mustBeRole('patient', 'PatientLogin.html')
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Prescription ID', 'Doctor ID', 'Record ID', 'IPFS Hash', 'Submitted At', 'Status', 'Content / Download']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    patient_id = str(session.get('user_id', ''))
    readDetails('prescription')
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        if row[1] == patient_id:
            hash_display = row[4]
            if isLegacyRecord(row[4]):
                hash_display = '[LEGACY] ' + row[4]
            output += '<tr><td>' + formatId('prescription', row[0]) + '</td>'
            output += '<td>' + formatId('doctor', row[2]) + '</td>'
            output += '<td>' + formatId('record', row[3]) + '</td>'
            output += '<td>' + hash_display + '</td>'
            output += '<td>' + formatLocalTime(row[6]) + '</td>'
            output += '<td>' + row[7] + '</td>'
            output += '<td>' + prescriptionContentDownloadCell(row[0], row[4], row[5]) + '</td></tr>'
    output += '</table>'
    return render_template('ViewPrescription.html', msg=output, back_link='/PatientScreen')