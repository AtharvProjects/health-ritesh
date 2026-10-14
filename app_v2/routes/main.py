from flask import Blueprint, render_template, request, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *
from app_v2.utils.services import *

main_bp = Blueprint('main', __name__)


@main_bp.route('/DownloadRecord/<record_id>')
def DownloadRecord(record_id):
    role = session.get('role')
    if role not in ('patient', 'doctor'):
        return render_template('index.html', msg='Please login to download records')
    web3, contract, account = getContract()
    record_id_int = parseId(record_id)
    record_patient_id = contract.functions.getRecordPatientId(record_id_int).call()
    ipfs_hash = contract.functions.getRecordIpfsHash(record_id_int).call()
    filename = contract.functions.getRecordFileName(record_id_int).call()
    if filename == '':
        record_type = contract.functions.getRecordType(record_id_int).call()
        safe_type = str(record_type).replace(' ', '_')
        filename = 'record_' + str(record_id) + '_' + safe_type + '.dat'
    if role == 'patient':
        err = mustBeRole('patient', 'PatientLogin.html')
        if err:
            return err
        if str(session.get('user_id', '')) != str(record_patient_id):
            return render_template('index.html', msg='You are not allowed to download this record')
    if role == 'doctor':
        err = mustBeRole('doctor', 'DoctorLogin.html')
        if err:
            return err
        doctor_id = session.get('user_id', 0)
        authorized = contract.functions.isDoctorAuthorized(int(doctor_id), record_id_int).call()
        if not authorized:
            return render_template('index.html', msg='You are not allowed to download this record')
        if str(record_id_int) not in session.get('accessed_records', []):
            msg = contract.functions.accessSharedRecord(doctor_id, record_id_int).transact({'from': account})
            web3.eth.wait_for_transaction_receipt(msg)
            if 'accessed_records' not in session:
                session['accessed_records'] = []
            session['accessed_records'].append(str(record_id_int))
            session.modified = True
            AppState.blockchain_tx_count += 1
    file_bytes = getDecryptedFileBytes(ipfs_hash, record_timing=True)
    return makeDownloadResponse(file_bytes, filename)

@main_bp.route('/DownloadPrescription/<prescription_id>')
def DownloadPrescription(prescription_id):
    role = session.get('role')
    if role not in ('patient', 'doctor'):
        return render_template('index.html', msg='Please login to download prescriptions')
    _, contract, _ = getContract()
    prescription_id_int = parseId(prescription_id)
    pres = contract.functions.prescriptionList(prescription_id_int).call()
    patient_id = pres[0]
    doctor_id = pres[1]
    ipfs_hash = pres[3]
    filename = pres[4]
    if filename == '':
        filename = 'prescription_' + str(prescription_id) + '.dat'
    if role == 'patient':
        err = mustBeRole('patient', 'PatientLogin.html')
        if err:
            return err
        if str(session.get('user_id', '')) != str(patient_id):
            return render_template('index.html', msg='You are not allowed to download this prescription')
        if str(prescription_id_int) not in session.get('viewed_prescriptions', []):
            logPrescriptionView(prescription_id_int, int(patient_id))
            if 'viewed_prescriptions' not in session:
                session['viewed_prescriptions'] = []
            session['viewed_prescriptions'].append(str(prescription_id_int))
            session.modified = True
    if role == 'doctor':
        err = mustBeRole('doctor', 'DoctorLogin.html')
        if err:
            return err
        if str(session.get('user_id', '')) != str(doctor_id):
            return render_template('index.html', msg='You are not allowed to download this prescription')
        if str(prescription_id_int) not in session.get('viewed_prescriptions', []):
            logPrescriptionView(prescription_id_int, int(doctor_id))
            if 'viewed_prescriptions' not in session:
                session['viewed_prescriptions'] = []
            session['viewed_prescriptions'].append(str(prescription_id_int))
            session.modified = True
    file_bytes = getDecryptedFileBytes(ipfs_hash, record_timing=True)
    return makeDownloadResponse(file_bytes, filename)

@main_bp.route('/')
def home():
    return render_template('index.html', msg='')