from flask import render_template, session, make_response
from app_v2.config import Config, AppState
from app_v2.utils.helpers import *
from app_v2.utils.blockchain import *
from app_v2.utils.crypto import *
from app_v2.utils.ipfs import *

def formatViewerId(viewer_id, prescription_id):
    _, contract, _ = getContract()
    pres = contract.functions.prescriptionList(int(prescription_id)).call()
    if int(viewer_id) == int(pres[0]):
        return formatId('patient', viewer_id)
    if int(viewer_id) == int(pres[1]):
        return formatId('doctor', viewer_id)
    return str(viewer_id)

def logPrescriptionView(prescription_id, viewer_id):
    saveDataBlockChain(str(prescription_id) + '#' + str(viewer_id), 'prescription_view')

def checkLogin(username, password, role):
    password_hash = hashPassword(password)
    status = 'none'
    user_id = 0
    if role == 'admin':
        readDetails('admin')
        arr = AppState.details.split('\n')
        for i in range(len(arr) - 1):
            row = arr[i].split('#')
            if row[0] == username and row[1] == password_hash:
                status = 'success'
                user_id = i
                break
    if role == 'doctor':
        readDetails('doctor')
        arr = AppState.details.split('\n')
        for i in range(len(arr) - 1):
            row = arr[i].split('#')
            if row[4] == username and row[5] == password_hash:
                status = 'success'
                user_id = int(row[0])
                break
    if role == 'patient':
        readDetails('patient')
        arr = AppState.details.split('\n')
        for i in range(len(arr) - 1):
            row = arr[i].split('#')
            if row[6] == username and row[7] == password_hash:
                status = 'success'
                user_id = int(row[0])
                break
    return (status, user_id)

def getOrganizationOptions():
    readDetails('organization')
    org_options = ''
    arr = AppState.details.split('\n')
    for i in range(len(arr) - 1):
        row = arr[i].split('#')
        org_options += "<option value='" + row[0] + "'>" + formatId('organization', row[0]) + ' - ' + row[1] + '</option>'
    return org_options

def getSharedRecordOptionsForDoctor(doctor_id):
    _, contract, _ = getContract()
    org_id = contract.functions.getDoctorOrganizationId(doctor_id).call()
    readDetails('record')
    record_arr = AppState.details.split('\n')
    options = ''
    for i in range(len(record_arr) - 1):
        row = record_arr[i].split('#')
        record_id = int(row[0])
        if contract.functions.isRecordSharedWithOrg(record_id, org_id).call():
            locked = contract.functions.isRecordLocked(record_id).call()
            if not locked:
                patient_name = contract.functions.getPatientName(int(row[1])).call()
                options += "<option value='" + row[0] + '#' + row[1] + "'>Record " + formatId('record', row[0]) + ' | ' + patient_name + ' (' + formatId('patient', row[1]) + ') | ' + row[3] + '</option>'
    return options

def getDoctorSharedRecords(doctor_id, filters=None):
    _, contract, _ = getContract()
    org_id = contract.functions.getDoctorOrganizationId(doctor_id).call()
    filters = filters or {}
    readDetails('record')
    record_arr = AppState.details.split('\n')
    records = []
    for i in range(len(record_arr) - 1):
        row = record_arr[i].split('#')
        record_id = int(row[0])
        if not contract.functions.isRecordSharedWithOrg(record_id, org_id).call():
            continue
        patient_name = contract.functions.getPatientName(int(row[1])).call()
        locked = contract.functions.isRecordLocked(record_id).call()
        if filters.get('patient_name'):
            search = filters['patient_name'].lower()
            formatted_patient = formatId('patient', row[1]).lower()
            if search not in patient_name.lower() and search not in row[1].lower() and (search not in formatted_patient):
                continue
        if filters.get('record_type'):
            if filters['record_type'].lower() not in row[3].lower():
                continue
        if filters.get('status') == 'open' and locked:
            continue
        if filters.get('status') == 'locked' and (not locked):
            continue
        records.append({'record_id': row[0], 'patient_id': row[1], 'patient_name': patient_name, 'ipfs': row[2], 'record_type': row[3], 'timestamp': row[4]})
    return records

def getRecordSharedOrganizations(record_id):
    _, contract, _ = getContract()
    readDetails('organization')
    org_arr = AppState.details.split('\n')
    shared = []
    for i in range(len(org_arr) - 1):
        row = org_arr[i].split('#')
        org_id = int(row[0])
        if contract.functions.isRecordSharedWithOrg(int(record_id), org_id).call():
            shared.append({'org_id': row[0], 'org_name': row[1], 'org_display': formatId('organization', row[0])})
    return shared

def getUnsharedOrganizationOptions(record_id):
    _, contract, _ = getContract()
    readDetails('organization')
    org_arr = AppState.details.split('\n')
    options = ''
    for i in range(len(org_arr) - 1):
        row = org_arr[i].split('#')
        org_id = int(row[0])
        if not contract.functions.isRecordSharedWithOrg(int(record_id), org_id).call():
            options += "<option value='" + row[0] + "'>" + formatId('organization', row[0]) + ' - ' + row[1] + '</option>'
    return options

def resolveViewerName(viewer_id, prescription_id):
    _, contract, _ = getContract()
    pres = contract.functions.prescriptionList(int(prescription_id)).call()
    if str(viewer_id) == str(pres[0]):
        return contract.functions.getPatientName(int(viewer_id)).call() + ' (Patient)'
    if str(viewer_id) == str(pres[1]):
        return contract.functions.getDoctorName(int(viewer_id)).call() + ' (Doctor)'
    if int(viewer_id) < contract.functions.patientCount().call():
        return contract.functions.getPatientName(int(viewer_id)).call() + ' (Patient)'
    if int(viewer_id) < contract.functions.doctorCount().call():
        return contract.functions.getDoctorName(int(viewer_id)).call() + ' (Doctor)'
    return 'User ' + str(viewer_id)

def getPrescriptionViewLogs():
    web3, contract, _ = getContract()
    logs = []
    events = contract.events.PrescriptionViewed.get_logs(fromBlock=0)
    for event in events:
        args = event['args']
        prescription_id = args['prescriptionId']
        viewer_id = args['viewerId']
        pres = contract.functions.prescriptionList(prescription_id).call()
        patient_name = contract.functions.getPatientName(pres[0]).call()
        doctor_name = contract.functions.getDoctorName(pres[1]).call()
        viewer_name = resolveViewerName(viewer_id, prescription_id)
        logs.append({'prescription_id': formatId('prescription', prescription_id), 'viewer_id': formatViewerId(viewer_id, prescription_id), 'viewer_name': viewer_name, 'patient_name': patient_name, 'doctor_name': doctor_name, 'record_id': formatId('record', pres[2])})
    return logs

def buildManageSharingPage(record_id, patient_id, status_msg=''):
    shared_orgs = getRecordSharedOrganizations(record_id)
    output = ''
    if status_msg != '':
        output += "<div class='alert alert-info'>" + status_msg + '</div>'
    output += '<p><b>Record ID:</b> ' + formatId('record', record_id) + ' | <b>Patient ID:</b> ' + formatId('patient', patient_id) + '</p>'
    output += "<h4 class='mt-3'>Currently Shared With</h4>"
    output += "<table class='" + TABLE_CLASS + "'><tr><th>Organization ID</th><th>Organization Name</th><th>Action</th></tr>"
    if len(shared_orgs) == 0:
        output += "<tr><td colspan='3'>Not shared with any organization</td></tr>"
    for org in shared_orgs:
        output += '<tr><td>' + org['org_display'] + '</td><td>' + org['org_name'] + '</td><td>'
        output += "<form method='post' action='/RevokeShareAction' class='d-inline'>" + "<input type='hidden' name='t1' value='" + str(record_id) + "'/>" + "<input type='hidden' name='t2' value='" + org['org_id'] + "'/>" + "<button type='submit' class='btn btn-danger btn-sm'>Revoke</button></form>"
        output += '</td></tr>'
    output += '</table>'
    output += "<h4 class='mt-4'>Share With New Organization</h4>"
    output += "<form method='post' action='/ShareRecordAction' id='shareRecordForm' class='mt-3'>"
    output += "<input type='hidden' name='t1' value='" + str(record_id) + "'/>"
    output += "<div class='card p-3 shadow-sm border border-light-subtle bg-white rounded mb-3'>"
    output += "<div class='d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2'>"
    output += "<input type='text' id='shareOrgSearch' class='form-control form-control-sm w-auto' placeholder='Filter clinics...'/>"
    output += "<div class='d-flex gap-2'>"
    output += "<button type='button' id='selectAllShareOrgs' class='btn btn-outline-primary btn-xs py-1 px-2 text-xs' style='font-size: 0.75rem;'>Select All</button>"
    output += "<button type='button' id='clearAllShareOrgs' class='btn btn-outline-secondary btn-xs py-1 px-2 text-xs' style='font-size: 0.75rem;'>Clear All</button>"
    output += '</div></div>'
    output += "<div id='shareOrgsContainer' class='overflow-y-auto pe-2' style='max-height: 180px;'>"
    readDetails('organization')
    _, contract, _ = getContract()
    org_arr = AppState.details.split('\n')
    unshared_count = 0
    for i in range(len(org_arr) - 1):
        row = org_arr[i].split('#')
        org_id = int(row[0])
        if not contract.functions.isRecordSharedWithOrg(int(record_id), org_id).call():
            unshared_count += 1
            output += "<div class='form-check mb-2 share-org-item'>" + "<input class='form-check-input share-org-cb' type='checkbox' name='t2' value='" + row[0] + "' id='share-cb-" + row[0] + "'>" + "<label class='form-check-label text-dark small fw-medium' for='share-cb-" + row[0] + "'>" + formatId('organization', row[0]) + ' - ' + row[1] + '</label></div>'
    if unshared_count == 0:
        output += "<p class='text-secondary small mb-0 p-2'>No new organizations available to share with.</p>"
    output += '</div></div>'
    output += "<button type='submit' class='btn btn-success btn-sm'>Share with Selected</button></form>"
    return output

def makeDownloadResponse(file_bytes, filename):
    response = make_response(file_bytes)
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = 'attachment; filename=' + filename
    return response

def formatContentDisplay(ipfs_hash, file_name='', max_len=200):
    file_name = str(file_name).strip()
    parts = []
    if isLegacyRecord(ipfs_hash):
        try:
            text = decryptFromIpfs(ipfs_hash)
        except Exception:
            text = ''
        if text:
            if len(text) > max_len:
                text = text[:max_len] + '...'
            parts.append("<div class='small mb-1'><b>Text:</b> " + escapeHtml(text) + '</div>')
        else:
            parts.append("<div class='small text-muted mb-1'>Preview unavailable. Use Download.</div>")
        return ''.join(parts)
    plain_bytes = safeGetDecryptedFileBytes(ipfs_hash)
    if plain_bytes is None:
        if file_name:
            parts.append("<div class='small mb-1'><b>File:</b> " + escapeHtml(file_name) + '</div>')
        parts.append("<div class='small text-muted mb-1'>Preview unavailable. Use Download.</div>")
        return ''.join(parts)
    if isTextContent(file_name, plain_bytes):
        text = plain_bytes.decode('utf-8', errors='replace').strip()
        if text:
            if len(text) > max_len:
                text = text[:max_len] + '...'
            parts.append("<div class='small mb-1'><b>Text:</b> " + escapeHtml(text) + '</div>')
    if file_name and file_name not in ('record_text.txt', 'prescription_text.txt'):
        parts.append("<div class='small mb-1'><b>File:</b> " + escapeHtml(file_name) + '</div>')
    elif not parts and file_name:
        parts.append("<div class='small mb-1'><b>File:</b> " + escapeHtml(file_name) + '</div>')
    if len(parts) == 0:
        parts.append("<div class='small text-muted mb-1'>Binary file. Use Download to view.</div>")
    return ''.join(parts)

def recordContentDownloadCell(record_id, ipfs_hash, file_name=''):
    if file_name == '':
        _, contract, _ = getContract()
        file_name = contract.functions.getRecordFileName(int(record_id)).call()
    url = '/DownloadRecord/' + formatId('record', record_id)
    return formatContentDisplay(ipfs_hash, file_name) + downloadButton(url)

def prescriptionContentDownloadCell(prescription_id, ipfs_hash, file_name=''):
    if file_name == '':
        _, contract, _ = getContract()
        pres = contract.functions.prescriptionList(int(prescription_id)).call()
        file_name = pres[4]
    url = '/DownloadPrescription/' + formatId('prescription', prescription_id)
    return formatContentDisplay(ipfs_hash, file_name) + downloadButton(url)

def getRecordPrescriptionStatus(record_id):
    _, contract, _ = getContract()
    record_id_int = int(record_id)
    locked = contract.functions.isRecordLocked(record_id_int).call()
    if not locked:
        return (False, 'Open - No prescription submitted yet')
    prescription_id = contract.functions.getPrescriptionByRecord(record_id_int).call()
    pres = contract.functions.prescriptionList(prescription_id).call()
    doctor_id = pres[1]
    doctor_name = contract.functions.getDoctorName(doctor_id).call()
    org_id = contract.functions.getDoctorOrganizationId(doctor_id).call()
    org_name = contract.functions.getOrganizationName(org_id).call()
    status = 'Locked - Prescription submitted by ' + doctor_name + ' (' + org_name + ')'
    return (True, status)

def prescriptionSubmitCell(record_id, patient_id, locked):
    if locked:
        return "<button type='button' class='btn btn-secondary btn-sm' disabled>Submit Prescription</button>"
    return "<a href='/SubmitPrescription/" + formatId('record', record_id) + '/' + formatId('patient', patient_id) + "' class='btn btn-success btn-sm'>Submit Prescription</a>"

def renderPrescriptionForm(record_id, patient_id, msg=''):
    _, contract, _ = getContract()
    record_type = contract.functions.getRecordType(int(record_id)).call()
    return render_template('SubmitPrescription.html', msg=msg, record_id=formatId('record', record_id), patient_id=formatId('patient', patient_id), record_type=str(record_type))

def buildSharedRecordsTable(doctor_id, filters=None):
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ['Record ID', 'Patient ID', 'Patient Name', 'IPFS Hash', 'Record Type', 'Uploaded At', 'Prescription Status', 'Content / Download', 'Submit Prescription']
    output += '<tr>'
    for header in headers:
        output += '<th>' + header + '</th>'
    output += '</tr>'
    shared_records = getDoctorSharedRecords(doctor_id, filters)
    if len(shared_records) == 0:
        output += "<tr><td colspan='9' class='text-center'>No shared records found</td></tr>"
    for row in shared_records:
        hash_display = row['ipfs']
        if isLegacyRecord(row['ipfs']):
            hash_display = '[LEGACY] ' + row['ipfs']
        locked, lock_status = getRecordPrescriptionStatus(row['record_id'])
        output += '<tr><td>' + formatId('record', row['record_id']) + '</td>'
        output += '<td>' + formatId('patient', row['patient_id']) + '</td>'
        output += '<td>' + row['patient_name'] + '</td>'
        output += '<td>' + hash_display + '</td>'
        output += '<td>' + row['record_type'] + '</td>'
        output += '<td>' + formatLocalTime(row['timestamp']) + '</td>'
        output += '<td>' + lock_status + '</td>'
        output += '<td>' + recordContentDownloadCell(row['record_id'], row['ipfs']) + '</td>'
        output += '<td>' + prescriptionSubmitCell(row['record_id'], row['patient_id'], locked) + '</td></tr>'
    output += '</table>'
    return output

def downloadButton(url):
    return "<a href='" + url + "' class='btn btn-primary btn-sm'>Download</a>"