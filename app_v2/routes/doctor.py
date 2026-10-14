from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *
from app_v2.utils.services import *

doctor_bp = Blueprint('doctor', __name__)


@doctor_bp.route('/DoctorScreen', methods=['GET'])
def DoctorScreen():
    err = mustBeRole('doctor', 'DoctorLogin.html')
    if err:
        return err
    username = session.get('username', '')
    msg = 'Doctor Dashboard'
    if username != '':
        msg = 'Doctor Dashboard | Logged in as: ' + username
    return render_template('DoctorScreen.html', msg=msg)

@doctor_bp.route('/ViewSharedRecords', methods=['GET'])
def ViewSharedRecords():
    err = mustBeRole('doctor', 'DoctorLogin.html')
    if err:
        return err
    doctor_id = session.get('user_id', 0)
    filters = {'patient_name': request.args.get('f_patient', '').strip(), 'record_type': request.args.get('f_type', '').strip(), 'status': request.args.get('f_status', '').strip()}
    status_msg = request.args.get('status_msg', '')
    return render_template('ViewSharedRecords.html', msg=buildSharedRecordsTable(doctor_id, filters), f_patient=filters['patient_name'], f_type=filters['record_type'], f_status=filters['status'], status_msg=status_msg)

@doctor_bp.route('/ViewPatientHistory', methods=['GET'])
def ViewPatientHistory():
    err = mustBeRole('doctor', 'DoctorLogin.html')
    if err:
        return err
    output = ''
    doctor_id = session.get('user_id', 0)
    shared_records = getDoctorSharedRecords(doctor_id)
    patients = {}
    for row in shared_records:
        patient_id = row['patient_id']
        if patient_id not in patients:
            patients[patient_id] = {'name': row['patient_name'], 'records': []}
        patients[patient_id]['records'].append(row)
    for patient_id in sorted(patients.keys()):
        patient_name = patients[patient_id]['name']
        output += "<h4 class='mt-3'>Patient: " + patient_name + ' (ID: ' + formatId('patient', patient_id) + ')</h4>'
        output += "<table class='" + TABLE_CLASS + "'>"
        output += '<tr><th>Record ID</th><th>Type</th><th>Uploaded At</th><th>Prescription Status</th><th>Content / Download</th><th>Submit Prescription</th></tr>'
        for row in patients[patient_id]['records']:
            locked, lock_status = getRecordPrescriptionStatus(row['record_id'])
            output += '<tr><td>' + formatId('record', row['record_id']) + '</td>'
            output += '<td>' + row['record_type'] + '</td>'
            output += '<td>' + formatLocalTime(row['timestamp']) + '</td>'
            output += '<td>' + lock_status + '</td>'
            output += '<td>' + recordContentDownloadCell(row['record_id'], row['ipfs']) + '</td>'
            output += '<td>' + prescriptionSubmitCell(row['record_id'], row['patient_id'], locked) + '</td></tr>'
        output += '</table><br/>'
    if output == '':
        output = 'No shared patient history found'
    return render_template('ViewPatientHistory.html', msg=output)

@doctor_bp.route('/SubmitPrescription/<record_id>/<patient_id>', methods=['GET'])
def SubmitPrescription(record_id, patient_id):
    err = mustBeRole('doctor', 'DoctorLogin.html')
    if err:
        return err
    doctor_id = session.get('user_id', 0)
    _, contract, _ = getContract()
    record_id_int = parseId(record_id)
    patient_id_int = parseId(patient_id)
    authorized = contract.functions.isDoctorAuthorized(int(doctor_id), record_id_int).call()
    if not authorized:
        return render_template('ViewSharedRecords.html', msg=buildSharedRecordsTable(doctor_id), status_msg='You are not authorized for this record', f_patient='', f_type='', f_status='')
    locked = contract.functions.isRecordLocked(record_id_int).call()
    if locked:
        return render_template('ViewSharedRecords.html', msg=buildSharedRecordsTable(doctor_id), status_msg='Prescription already submitted for this record', f_patient='', f_type='', f_status='')
    return renderPrescriptionForm(record_id_int, patient_id_int)

@doctor_bp.route('/SubmitPrescriptionAction', methods=['POST'])
def SubmitPrescriptionAction():
    err = mustBeRole('doctor', 'DoctorLogin.html')
    if err:
        return err
    if request.method == 'POST':
        selected = request.form['t1']
        prescription_text = request.form.get('t3', '')
        file = request.files.get('t2')
        doctor_id = session.get('user_id', 0)
        table = buildSharedRecordsTable(doctor_id)
        if selected == '' or '#' not in selected:
            return render_template('ViewSharedRecords.html', msg=table, status_msg='Invalid record selected', f_patient='', f_type='', f_status='')
        record_part, patient_part = selected.split('#')
        record_id = parseId(record_part)
        patient_id = parseId(patient_part)
        if file and file.filename:
            raw_data = file.read()
            original_filename = file.filename
        elif prescription_text.strip() != '':
            raw_data = prescription_text.encode('utf-8')
            original_filename = 'prescription_text.txt'
        else:
            return renderPrescriptionForm(record_id, patient_id, msg='Please upload a file or enter prescription text')
        web3, contract, account = getContract()
        authorized = contract.functions.isDoctorAuthorized(int(doctor_id), int(record_id)).call()
        if not authorized:
            return render_template('ViewSharedRecords.html', msg=table, status_msg='You are not authorized for this record', f_patient='', f_type='', f_status='')
        locked = contract.functions.isRecordLocked(int(record_id)).call()
        if locked:
            return render_template('ViewSharedRecords.html', msg=table, status_msg='Prescription already submitted for this record', f_patient='', f_type='', f_status='')
        encrypted_data = doubleEncrypt(raw_data)
        ipfs_hash = uploadToPinata(encrypted_data, 'encrypted_prescription.b64')
        data = str(doctor_id) + '#' + str(patient_id) + '#' + str(record_id) + '#' + ipfs_hash + '#' + original_filename
        saveDataBlockChain(data, 'prescription')
        table = buildSharedRecordsTable(doctor_id)
        return render_template('ViewSharedRecords.html', msg=table, status_msg='Prescription submitted for Record ID ' + formatId('record', record_id) + ' and Patient ID ' + formatId('patient', patient_id), f_patient='', f_type='', f_status='')

@doctor_bp.route('/ViewDoctorPrescription', methods=['GET'])
def ViewDoctorPrescription():
    err = mustBeRole('doctor', 'DoctorLogin.html')
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Prescription ID', 'Patient ID', 'Record ID', 'IPFS Hash', 'Submitted At', 'Status', 'Content / Download']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    doctor_id = str(session.get('user_id', ''))
    readDetails('prescription')
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        if row[2] == doctor_id:
            hash_display = row[4]
            if isLegacyRecord(row[4]):
                hash_display = '[LEGACY] ' + row[4]
            output += '<tr><td>' + formatId('prescription', row[0]) + '</td>'
            output += '<td>' + formatId('patient', row[1]) + '</td>'
            output += '<td>' + formatId('record', row[3]) + '</td>'
            output += '<td>' + hash_display + '</td>'
            output += '<td>' + formatLocalTime(row[6]) + '</td>'
            output += '<td>' + row[7] + '</td>'
            output += '<td>' + prescriptionContentDownloadCell(row[0], row[4], row[5]) + '</td></tr>'
    output += '</table>'
    return render_template('ViewPrescription.html', msg=output, back_link='/DoctorScreen')