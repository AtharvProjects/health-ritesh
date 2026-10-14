from flask import Flask, render_template, request, session, make_response
from datetime import datetime
import json
import hashlib
import os
import time
import pickle
import base64
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from phe import paillier
from phe.paillier import EncryptedNumber
from web3 import Web3, HTTPProvider

app = Flask(__name__)
app.secret_key = "healthcare_secret_key"

details = ""
encryption_times = []
decryption_times = []
blockchain_tx_count = 0
TABLE_CLASS = "table table-bordered table-striped table-hover table-sm"
KEYS_FOLDER = "keys"
os.makedirs(KEYS_FOLDER, exist_ok=True)

# Pinata IPFS keys - get from https://pinata.cloud
PINATA_API_KEY = "1bb8e4d7ff828d8dd537"
PINATA_SECRET_KEY = "b98bfe6db5f5fc1512a7f2060bc24d397aa8765ef49f12eb80463692c80fca29"

# Blockchain settings
blockchain_address = "http://127.0.0.1:8545"
compiled_contract_path = "build/contracts/HealthcareRecords.json"
try:
    with open(compiled_contract_path) as _f:
        _net_id = list(json.load(_f)["networks"].keys())[-1]
        _f.seek(0)
        deployed_contract_address = json.load(_f)["networks"][_net_id]["address"]
except Exception:
    deployed_contract_address = "0x345cA3e014Aaf5dcA488057592ee47305D9B3e10"

aes_key = None
paillier_public_key = None
paillier_private_key = None


def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()


def formatLocalTime(timestamp):
    if str(timestamp).isdigit():
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    return str(timestamp)


ID_PREFIXES = {
    "admin": "ADM",
    "organization": "ORG",
    "doctor": "DOC",
    "patient": "PAT",
    "record": "REC",
    "prescription": "PRE",
    "sharing": "SHR",
    "access": "ACC",
}


def formatId(entity_type, id_value):
    prefix = ID_PREFIXES[entity_type]
    return prefix + str(int(id_value)).zfill(3)


def parseId(id_value):
    id_str = str(id_value).strip().upper()
    for prefix in ID_PREFIXES.values():
        if id_str.startswith(prefix):
            num_part = id_str[len(prefix) :]
            if num_part.isdigit():
                return int(num_part)
    return int(id_str)


def isFormattedId(value):
    id_str = str(value).strip().upper()
    for prefix in ID_PREFIXES.values():
        if id_str.startswith(prefix):
            num_part = id_str[len(prefix) :]
            if num_part.isdigit():
                return True
    return False


def formatViewerId(viewer_id, prescription_id):
    _, contract, _ = getContract()
    pres = contract.functions.prescriptionList(int(prescription_id)).call()
    if int(viewer_id) == int(pres[0]):
        return formatId("patient", viewer_id)
    if int(viewer_id) == int(pres[1]):
        return formatId("doctor", viewer_id)
    return str(viewer_id)


def isLegacyRecord(stored_hash):
    stored_hash = str(stored_hash).strip()
    return stored_hash.startswith("uploads/") or stored_hash.startswith("uploads\\")


def mustBeRole(role, login_template, msg="Please login first"):
    if session.get("role") != role:
        return render_template(login_template, msg=msg)
    return None


def logPrescriptionView(prescription_id, viewer_id):
    saveDataBlockChain(str(prescription_id) + "#" + str(viewer_id), "prescription_view")


def loadOrCreateKeys():
    global aes_key, paillier_public_key, paillier_private_key

    aes_file = os.path.join(KEYS_FOLDER, "aes_key.bin")
    paillier_file = os.path.join(KEYS_FOLDER, "paillier_keys.pkl")

    if os.path.exists(aes_file):
        aes_key = open(aes_file, "rb").read()
    else:
        aes_key = get_random_bytes(32)
        open(aes_file, "wb").write(aes_key)

    if os.path.exists(paillier_file):
        key_data = pickle.load(open(paillier_file, "rb"))
        paillier_public_key = key_data["public"]
        paillier_private_key = key_data["private"]
    else:
        paillier_public_key, paillier_private_key = paillier.generate_paillier_keypair(n_length=2048)
        pickle.dump(
            {"public": paillier_public_key, "private": paillier_private_key},
            open(paillier_file, "wb"),
        )


def aesEncrypt(data_bytes):
    cipher = AES.new(aes_key, AES.MODE_CBC)
    encrypted = cipher.encrypt(pad(data_bytes, AES.block_size))
    return cipher.iv + encrypted


def aesDecrypt(data_bytes):
    iv = data_bytes[:16]
    encrypted = data_bytes[16:]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(encrypted), AES.block_size)


def paillierEncrypt(data_bytes):
    chunk_size = 100
    chunks = []
    for i in range(0, len(data_bytes), chunk_size):
        chunk = data_bytes[i : i + chunk_size]
        number = int.from_bytes(chunk, "big")
        encrypted_number = paillier_public_key.encrypt(number)
        chunks.append(str(encrypted_number.ciphertext()))
    return json.dumps({"chunks": chunks, "total_length": len(data_bytes)})


def paillierDecrypt(data_json):
    data = json.loads(data_json)
    result = b""
    for chunk in data["chunks"]:
        encrypted_number = EncryptedNumber(paillier_public_key, int(chunk))
        number = paillier_private_key.decrypt(encrypted_number)
        chunk_bytes = number.to_bytes((number.bit_length() + 7) // 8, "big")
        result += chunk_bytes
    return result[: data["total_length"]]


def doubleEncrypt(data_bytes):
    start = time.time()
    aes_data = aesEncrypt(data_bytes)
    final_data = paillierEncrypt(aes_data)
    encrypted_text = base64.b64encode(final_data.encode("utf-8")).decode("ascii")
    encryption_times.append(round((time.time() - start) * 1000, 2))
    return encrypted_text.encode("utf-8")


def doubleDecrypt(data_bytes, record_timing=False):
    start = time.time()
    if len(data_bytes) == 0:
        raise Exception("Downloaded file is empty")

    text = data_bytes.decode("utf-8", errors="ignore").strip()
    if text.startswith("{"):
        paillier_data = text
    else:
        paillier_data = base64.b64decode(text).decode("utf-8")

    if not paillier_data.startswith("{"):
        raise Exception("Invalid encrypted data - re-upload the record")

    aes_data = paillierDecrypt(paillier_data)
    plain_data = aesDecrypt(aes_data)
    if record_timing:
        decryption_times.append(round((time.time() - start) * 1000, 2))
    return plain_data


def uploadToPinata(data_bytes, filename):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {
        "pinata_api_key": PINATA_API_KEY,
        "pinata_secret_api_key": PINATA_SECRET_KEY,
    }
    files = {"file": (filename, data_bytes)}
    response = requests.post(url, files=files, headers=headers, timeout=60)
    response_json = response.json()
    if "IpfsHash" not in response_json:
        raise Exception("Pinata upload failed: " + str(response_json))
    return response_json["IpfsHash"]


def downloadFromIpfs(ipfs_hash):
    ipfs_hash = str(ipfs_hash).strip()

    if ipfs_hash.startswith("uploads/") or ipfs_hash.startswith("uploads\\"):
        if os.path.exists(ipfs_hash):
            return open(ipfs_hash, "rb").read()
        raise Exception("Old local file not found - please re-upload record")

    gateways = [
        "https://gateway.pinata.cloud/ipfs/",
        "https://ipfs.io/ipfs/",
        "https://dweb.link/ipfs/",
    ]

    for gateway in gateways:
        response = requests.get(gateway + ipfs_hash, timeout=60)
        if response.status_code == 200 and len(response.content) > 0:
            return response.content

    raise Exception("Could not download file from IPFS - check hash or wait and retry")


def getContract():
    web3 = Web3(HTTPProvider(blockchain_address))
    accounts = web3.eth.accounts
    if len(accounts) == 0:
        raise Exception("Ganache is not running or no accounts found")
    account = accounts[0]
    with open(compiled_contract_path) as file:
        contract_json = json.load(file)
        contract_abi = contract_json["abi"]
    file.close()
    contract = web3.eth.contract(address=deployed_contract_address, abi=contract_abi)
    return web3, contract, account


def readDetails(contract_type):
    global details
    details = ""
    web3, contract, account = getContract()

    if contract_type == "admin":
        count = contract.functions.adminCount().call()
        for i in range(count):
            username = contract.functions.getAdminUsername(i).call()
            password = contract.functions.getAdminPasswordHash(i).call()
            details += str(username) + "#" + str(password) + "\n"

    if contract_type == "organization":
        count = contract.functions.organizationCount().call()
        for i in range(count):
            name = contract.functions.getOrganizationName(i).call()
            address = contract.functions.getOrganizationAddress(i).call()
            contact = contract.functions.getOrganizationContact(i).call()
            details += str(i) + "#" + str(name) + "#" + str(address) + "#" + str(contact) + "\n"

    if contract_type == "doctor":
        count = contract.functions.doctorCount().call()
        for i in range(count):
            name = contract.functions.getDoctorName(i).call()
            spec = contract.functions.getDoctorSpecialization(i).call()
            org_id = contract.functions.getDoctorOrganizationId(i).call()
            username = contract.functions.getDoctorUsername(i).call()
            password = contract.functions.getDoctorPasswordHash(i).call()
            details += str(i) + "#" + str(name) + "#" + str(spec) + "#" + str(org_id) + "#" + str(username) + "#" + str(password) + "\n"

    if contract_type == "patient":
        count = contract.functions.patientCount().call()
        for i in range(count):
            name = contract.functions.getPatientName(i).call()
            gender = contract.functions.getPatientGender(i).call()
            dob = contract.functions.getPatientDob(i).call()
            contact = contract.functions.getPatientContact(i).call()
            address = contract.functions.getPatientAddress(i).call()
            username = contract.functions.getPatientUsername(i).call()
            password = contract.functions.getPatientPasswordHash(i).call()
            details += str(i) + "#" + str(name) + "#" + str(gender) + "#" + str(dob) + "#" + str(contact) + "#" + str(address) + "#" + str(username) + "#" + str(password) + "\n"

    if contract_type == "record":
        count = contract.functions.recordCount().call()
        for i in range(count):
            patient_id = contract.functions.getRecordPatientId(i).call()
            ipfs_hash = contract.functions.getRecordIpfsHash(i).call()
            record_type = contract.functions.getRecordType(i).call()
            timestamp = contract.functions.getRecordTimestamp(i).call()
            locked = contract.functions.isRecordLocked(i).call()
            file_name = contract.functions.getRecordFileName(i).call()
            details += (
                str(i)
                + "#"
                + str(patient_id)
                + "#"
                + str(ipfs_hash)
                + "#"
                + str(record_type)
                + "#"
                + str(timestamp)
                + "#"
                + str(locked)
                + "#"
                + str(file_name)
                + "\n"
            )

    if contract_type == "sharing":
        count = contract.functions.sharingCount().call()
        for i in range(count):
            record_id = contract.functions.getSharingRecordId(i).call()
            patient_id = contract.functions.getSharingPatientId(i).call()
            org_id = contract.functions.getSharingOrganizationId(i).call()
            shared_time = contract.functions.getSharingTimestamp(i).call()
            details += str(i) + "#" + str(record_id) + "#" + str(patient_id) + "#" + str(org_id) + "#" + str(shared_time) + "\n"

    if contract_type == "prescription":
        count = contract.functions.prescriptionCount().call()
        for i in range(count):
            pres = contract.functions.prescriptionList(i).call()
            details += (
                str(i)
                + "#"
                + str(pres[0])
                + "#"
                + str(pres[1])
                + "#"
                + str(pres[2])
                + "#"
                + str(pres[3])
                + "#"
                + str(pres[4])
                + "#"
                + str(pres[5])
                + "#"
                + str(pres[6])
                + "\n"
            )

    if contract_type == "access":
        count = contract.functions.accessCount().call()
        for i in range(count):
            doctor_id = contract.functions.getAccessDoctorId(i).call()
            record_id = contract.functions.getAccessRecordId(i).call()
            patient_id = contract.functions.getAccessPatientId(i).call()
            org_id = contract.functions.getAccessOrganizationId(i).call()
            access_time = contract.functions.getAccessTimestamp(i).call()
            details += str(i) + "#" + str(doctor_id) + "#" + str(record_id) + "#" + str(patient_id) + "#" + str(org_id) + "#" + str(access_time) + "\n"

    if contract_type == "analytics":
        org_count = contract.functions.organizationCount().call()
        doctor_count = contract.functions.doctorCount().call()
        patient_count = contract.functions.patientCount().call()
        record_count = contract.functions.recordCount().call()
        sharing_count = contract.functions.sharingCount().call()
        prescription_count = contract.functions.prescriptionCount().call()
        access_count = contract.functions.accessCount().call()
        avg_encrypt = 0
        avg_decrypt = 0
        if len(encryption_times) > 0:
            avg_encrypt = round(sum(encryption_times) / len(encryption_times), 2)
        if len(decryption_times) > 0:
            avg_decrypt = round(sum(decryption_times) / len(decryption_times), 2)
        details = (
            str(org_count)
            + "#"
            + str(doctor_count)
            + "#"
            + str(patient_count)
            + "#"
            + str(record_count)
            + "#"
            + str(sharing_count)
            + "#"
            + str(prescription_count)
            + "#"
            + str(access_count)
            + "#"
            + str(avg_encrypt)
            + "#"
            + str(avg_decrypt)
            + "#"
            + str(blockchain_tx_count)
        )


def saveDataBlockChain(currentData, contract_type):
    global details, blockchain_tx_count
    details = ""
    web3, contract, account = getContract()
    arr = currentData.split("#")
    tx = {"from": account}

    if contract_type == "admin":
        msg = contract.functions.saveAdmin(arr[0], arr[1]).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "organization":
        msg = contract.functions.saveOrganization(arr[0], arr[1], arr[2]).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "doctor":
        msg = contract.functions.saveDoctor(arr[0], arr[1], int(arr[2]), arr[3], arr[4]).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "patient":
        msg = contract.functions.savePatient(arr[0], arr[1], arr[2], arr[3], arr[4], arr[5], arr[6]).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "record":
        msg = contract.functions.saveMedicalRecord(int(arr[0]), arr[1], arr[2], arr[3]).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "sharing":
        msg = contract.functions.shareRecord(int(arr[0]), int(arr[1]), int(arr[2])).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "revoke_share":
        msg = contract.functions.revokeShare(int(arr[0]), int(arr[1]), int(arr[2])).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "prescription":
        msg = contract.functions.savePrescription(int(arr[0]), int(arr[1]), int(arr[2]), arr[3], arr[4]).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1

    if contract_type == "prescription_view":
        msg = contract.functions.logPrescriptionViewed(int(arr[0]), int(arr[1])).transact(tx)
        web3.eth.wait_for_transaction_receipt(msg)
        blockchain_tx_count += 1


def checkLogin(username, password, role):
    password_hash = hashPassword(password)
    status = "none"
    user_id = 0

    if role == "admin":
        readDetails("admin")
        arr = details.split("\n")
        for i in range(len(arr) - 1):
            row = arr[i].split("#")
            if row[0] == username and row[1] == password_hash:
                status = "success"
                user_id = i
                break

    if role == "doctor":
        readDetails("doctor")
        arr = details.split("\n")
        for i in range(len(arr) - 1):
            row = arr[i].split("#")
            if row[4] == username and row[5] == password_hash:
                status = "success"
                user_id = int(row[0])
                break

    if role == "patient":
        readDetails("patient")
        arr = details.split("\n")
        for i in range(len(arr) - 1):
            row = arr[i].split("#")
            if row[6] == username and row[7] == password_hash:
                status = "success"
                user_id = int(row[0])
                break

    return status, user_id


def getOrganizationOptions():
    readDetails("organization")
    org_options = ""
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        org_options += (
            "<option value='"
            + row[0]
            + "'>"
            + formatId("organization", row[0])
            + " - "
            + row[1]
            + "</option>"
        )
    return org_options


def getSharedRecordOptionsForDoctor(doctor_id):
    _, contract, _ = getContract()
    org_id = contract.functions.getDoctorOrganizationId(doctor_id).call()
    readDetails("record")
    record_arr = details.split("\n")
    options = ""
    for i in range(len(record_arr) - 1):
        row = record_arr[i].split("#")
        record_id = int(row[0])
        if contract.functions.isRecordSharedWithOrg(record_id, org_id).call():
            locked = contract.functions.isRecordLocked(record_id).call()
            if not locked:
                patient_name = contract.functions.getPatientName(int(row[1])).call()
                options += (
                    "<option value='"
                    + row[0]
                    + "#"
                    + row[1]
                    + "'>Record "
                    + formatId("record", row[0])
                    + " | "
                    + patient_name
                    + " ("
                    + formatId("patient", row[1])
                    + ") | "
                    + row[3]
                    + "</option>"
                )
    return options


def getDoctorSharedRecords(doctor_id, filters=None):
    _, contract, _ = getContract()
    org_id = contract.functions.getDoctorOrganizationId(doctor_id).call()
    filters = filters or {}
    readDetails("record")
    record_arr = details.split("\n")
    records = []
    for i in range(len(record_arr) - 1):
        row = record_arr[i].split("#")
        record_id = int(row[0])
        if not contract.functions.isRecordSharedWithOrg(record_id, org_id).call():
            continue
        patient_name = contract.functions.getPatientName(int(row[1])).call()
        locked = contract.functions.isRecordLocked(record_id).call()
        if filters.get("patient_name"):
            search = filters["patient_name"].lower()
            formatted_patient = formatId("patient", row[1]).lower()
            if (
                search not in patient_name.lower()
                and search not in row[1].lower()
                and search not in formatted_patient
            ):
                continue
        if filters.get("record_type"):
            if filters["record_type"].lower() not in row[3].lower():
                continue
        if filters.get("status") == "open" and locked:
            continue
        if filters.get("status") == "locked" and not locked:
            continue
        records.append(
            {
                "record_id": row[0],
                "patient_id": row[1],
                "patient_name": patient_name,
                "ipfs": row[2],
                "record_type": row[3],
                "timestamp": row[4],
            }
        )
    return records


def getRecordSharedOrganizations(record_id):
    _, contract, _ = getContract()
    readDetails("organization")
    org_arr = details.split("\n")
    shared = []
    for i in range(len(org_arr) - 1):
        row = org_arr[i].split("#")
        org_id = int(row[0])
        if contract.functions.isRecordSharedWithOrg(int(record_id), org_id).call():
            shared.append(
                {
                    "org_id": row[0],
                    "org_name": row[1],
                    "org_display": formatId("organization", row[0]),
                }
            )
    return shared


def getUnsharedOrganizationOptions(record_id):
    _, contract, _ = getContract()
    readDetails("organization")
    org_arr = details.split("\n")
    options = ""
    for i in range(len(org_arr) - 1):
        row = org_arr[i].split("#")
        org_id = int(row[0])
        if not contract.functions.isRecordSharedWithOrg(int(record_id), org_id).call():
            options += (
                "<option value='"
                + row[0]
                + "'>"
                + formatId("organization", row[0])
                + " - "
                + row[1]
                + "</option>"
            )
    return options


def resolveViewerName(viewer_id, prescription_id):
    _, contract, _ = getContract()
    pres = contract.functions.prescriptionList(int(prescription_id)).call()
    if str(viewer_id) == str(pres[0]):
        return contract.functions.getPatientName(int(viewer_id)).call() + " (Patient)"
    if str(viewer_id) == str(pres[1]):
        return contract.functions.getDoctorName(int(viewer_id)).call() + " (Doctor)"
    if int(viewer_id) < contract.functions.patientCount().call():
        return contract.functions.getPatientName(int(viewer_id)).call() + " (Patient)"
    if int(viewer_id) < contract.functions.doctorCount().call():
        return contract.functions.getDoctorName(int(viewer_id)).call() + " (Doctor)"
    return "User " + str(viewer_id)


def getPrescriptionViewLogs():
    web3, contract, _ = getContract()
    logs = []
    events = contract.events.PrescriptionViewed.get_logs(fromBlock=0)
    for event in events:
        args = event["args"]
        prescription_id = args["prescriptionId"]
        viewer_id = args["viewerId"]
        pres = contract.functions.prescriptionList(prescription_id).call()
        patient_name = contract.functions.getPatientName(pres[0]).call()
        doctor_name = contract.functions.getDoctorName(pres[1]).call()
        viewer_name = resolveViewerName(viewer_id, prescription_id)
        logs.append(
            {
                "prescription_id": formatId("prescription", prescription_id),
                "viewer_id": formatViewerId(viewer_id, prescription_id),
                "viewer_name": viewer_name,
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "record_id": formatId("record", pres[2]),
            }
        )
    return logs


def buildManageSharingPage(record_id, patient_id, status_msg=""):
    shared_orgs = getRecordSharedOrganizations(record_id)
    output = ""
    if status_msg != "":
        output += "<div class='alert alert-info'>" + status_msg + "</div>"
    output += (
        "<p><b>Record ID:</b> "
        + formatId("record", record_id)
        + " | <b>Patient ID:</b> "
        + formatId("patient", patient_id)
        + "</p>"
    )
    output += "<h4 class='mt-3'>Currently Shared With</h4>"
    output += "<table class='" + TABLE_CLASS + "'><tr><th>Organization ID</th><th>Organization Name</th><th>Action</th></tr>"
    if len(shared_orgs) == 0:
        output += "<tr><td colspan='3'>Not shared with any organization</td></tr>"
    for org in shared_orgs:
        output += "<tr><td>" + org["org_display"] + "</td><td>" + org["org_name"] + "</td><td>"
        output += (
            "<form method='post' action='/RevokeShareAction' class='d-inline'>"
            + "<input type='hidden' name='t1' value='"
            + str(record_id)
            + "'/>"
            + "<input type='hidden' name='t2' value='"
            + org["org_id"]
            + "'/>"
            + "<button type='submit' class='btn btn-danger btn-sm'>Revoke</button></form>"
        )
        output += "</td></tr>"
    output += "</table>"
    output += "<h4 class='mt-4'>Share With New Organization</h4>"
    output += "<form method='post' action='/ShareRecordAction' id='shareRecordForm' class='mt-3'>"
    output += "<input type='hidden' name='t1' value='" + str(record_id) + "'/>"
    
    # Checkbox layout box
    output += "<div class='card p-3 shadow-sm border border-light-subtle bg-white rounded mb-3'>"
    output += "<div class='d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2'>"
    output += "<input type='text' id='shareOrgSearch' class='form-control form-control-sm w-auto' placeholder='Filter clinics...'/>"
    output += "<div class='d-flex gap-2'>"
    output += "<button type='button' id='selectAllShareOrgs' class='btn btn-outline-primary btn-xs py-1 px-2 text-xs' style='font-size: 0.75rem;'>Select All</button>"
    output += "<button type='button' id='clearAllShareOrgs' class='btn btn-outline-secondary btn-xs py-1 px-2 text-xs' style='font-size: 0.75rem;'>Clear All</button>"
    output += "</div></div>"
    
    output += "<div id='shareOrgsContainer' class='overflow-y-auto pe-2' style='max-height: 180px;'>"
    
    readDetails("organization")
    _, contract, _ = getContract()
    org_arr = details.split("\n")
    unshared_count = 0
    for i in range(len(org_arr) - 1):
        row = org_arr[i].split("#")
        org_id = int(row[0])
        if not contract.functions.isRecordSharedWithOrg(int(record_id), org_id).call():
            unshared_count += 1
            output += (
                "<div class='form-check mb-2 share-org-item'>"
                + "<input class='form-check-input share-org-cb' type='checkbox' name='t2' value='"
                + row[0]
                + "' id='share-cb-"
                + row[0]
                + "'>"
                + "<label class='form-check-label text-dark small fw-medium' for='share-cb-"
                + row[0]
                + "'>"
                + formatId("organization", row[0])
                + " - "
                + row[1]
                + "</label></div>"
            )
            
    if unshared_count == 0:
        output += "<p class='text-secondary small mb-0 p-2'>No new organizations available to share with.</p>"
        
    output += "</div></div>"
    output += "<button type='submit' class='btn btn-success btn-sm'>Share with Selected</button></form>"
    return output


def decryptFromIpfs(ipfs_hash):
    ipfs_hash = str(ipfs_hash).strip()

    if ipfs_hash.startswith("uploads/") or ipfs_hash.startswith("uploads\\"):
        if os.path.exists(ipfs_hash):
            return open(ipfs_hash, "r", encoding="utf-8", errors="replace").read()
        return "Old local record - please re-upload with encryption"

    encrypted_data = downloadFromIpfs(ipfs_hash)
    plain_data = doubleDecrypt(encrypted_data, record_timing=False)
    return plain_data.decode("utf-8", errors="replace")


def getDecryptedFileBytes(stored_hash, record_timing=False):
    ipfs_hash = str(stored_hash).strip()
    if isLegacyRecord(ipfs_hash):
        if os.path.exists(ipfs_hash):
            return open(ipfs_hash, "rb").read()
        return b"Old local record - please re-upload with encryption"
    encrypted_data = downloadFromIpfs(ipfs_hash)
    return doubleDecrypt(encrypted_data, record_timing=record_timing)


def makeDownloadResponse(file_bytes, filename):
    response = make_response(file_bytes)
    response.headers["Content-Type"] = "application/octet-stream"
    response.headers["Content-Disposition"] = "attachment; filename=" + filename
    return response


def escapeHtml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def isTextContent(file_name, plain_bytes):
    name = str(file_name).lower()
    if name.endswith(".txt") or name in ("record_text.txt", "prescription_text.txt"):
        return True
    text = plain_bytes.decode("utf-8", errors="replace")
    if len(text) == 0:
        return False
    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    return printable / len(text) > 0.85


def safeGetDecryptedFileBytes(ipfs_hash):
    try:
        return getDecryptedFileBytes(ipfs_hash)
    except Exception:
        return None


def formatContentDisplay(ipfs_hash, file_name="", max_len=200):
    file_name = str(file_name).strip()
    parts = []

    if isLegacyRecord(ipfs_hash):
        try:
            text = decryptFromIpfs(ipfs_hash)
        except Exception:
            text = ""
        if text:
            if len(text) > max_len:
                text = text[:max_len] + "..."
            parts.append("<div class='small mb-1'><b>Text:</b> " + escapeHtml(text) + "</div>")
        else:
            parts.append("<div class='small text-muted mb-1'>Preview unavailable. Use Download.</div>")
        return "".join(parts)

    plain_bytes = safeGetDecryptedFileBytes(ipfs_hash)
    if plain_bytes is None:
        if file_name:
            parts.append("<div class='small mb-1'><b>File:</b> " + escapeHtml(file_name) + "</div>")
        parts.append("<div class='small text-muted mb-1'>Preview unavailable. Use Download.</div>")
        return "".join(parts)

    if isTextContent(file_name, plain_bytes):
        text = plain_bytes.decode("utf-8", errors="replace").strip()
        if text:
            if len(text) > max_len:
                text = text[:max_len] + "..."
            parts.append("<div class='small mb-1'><b>Text:</b> " + escapeHtml(text) + "</div>")

    if file_name and file_name not in ("record_text.txt", "prescription_text.txt"):
        parts.append("<div class='small mb-1'><b>File:</b> " + escapeHtml(file_name) + "</div>")
    elif not parts and file_name:
        parts.append("<div class='small mb-1'><b>File:</b> " + escapeHtml(file_name) + "</div>")

    if len(parts) == 0:
        parts.append("<div class='small text-muted mb-1'>Binary file. Use Download to view.</div>")

    return "".join(parts)


def recordContentDownloadCell(record_id, ipfs_hash, file_name=""):
    if file_name == "":
        _, contract, _ = getContract()
        file_name = contract.functions.getRecordFileName(int(record_id)).call()
    url = "/DownloadRecord/" + formatId("record", record_id)
    return formatContentDisplay(ipfs_hash, file_name) + downloadButton(url)


def prescriptionContentDownloadCell(prescription_id, ipfs_hash, file_name=""):
    if file_name == "":
        _, contract, _ = getContract()
        pres = contract.functions.prescriptionList(int(prescription_id)).call()
        file_name = pres[4]
    url = "/DownloadPrescription/" + formatId("prescription", prescription_id)
    return formatContentDisplay(ipfs_hash, file_name) + downloadButton(url)


def getRecordPrescriptionStatus(record_id):
    _, contract, _ = getContract()
    record_id_int = int(record_id)
    locked = contract.functions.isRecordLocked(record_id_int).call()
    if not locked:
        return False, "Open - No prescription submitted yet"

    prescription_id = contract.functions.getPrescriptionByRecord(record_id_int).call()
    pres = contract.functions.prescriptionList(prescription_id).call()
    doctor_id = pres[1]
    doctor_name = contract.functions.getDoctorName(doctor_id).call()
    org_id = contract.functions.getDoctorOrganizationId(doctor_id).call()
    org_name = contract.functions.getOrganizationName(org_id).call()
    status = (
        "Locked - Prescription submitted by "
        + doctor_name
        + " ("
        + org_name
        + ")"
    )
    return True, status


def prescriptionSubmitCell(record_id, patient_id, locked):
    if locked:
        return "<button type='button' class='btn btn-secondary btn-sm' disabled>Submit Prescription</button>"
    return (
        "<a href='/SubmitPrescription/"
        + formatId("record", record_id)
        + "/"
        + formatId("patient", patient_id)
        + "' class='btn btn-success btn-sm'>Submit Prescription</a>"
    )


def renderPrescriptionForm(record_id, patient_id, msg=""):
    _, contract, _ = getContract()
    record_type = contract.functions.getRecordType(int(record_id)).call()
    return render_template(
        "SubmitPrescription.html",
        msg=msg,
        record_id=formatId("record", record_id),
        patient_id=formatId("patient", patient_id),
        record_type=str(record_type),
    )


def buildSharedRecordsTable(doctor_id, filters=None):
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = [
        "Record ID",
        "Patient ID",
        "Patient Name",
        "IPFS Hash",
        "Record Type",
        "Uploaded At",
        "Prescription Status",
        "Content / Download",
        "Submit Prescription",
    ]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    shared_records = getDoctorSharedRecords(doctor_id, filters)
    if len(shared_records) == 0:
        output += "<tr><td colspan='9' class='text-center'>No shared records found</td></tr>"
    for row in shared_records:
        hash_display = row["ipfs"]
        if isLegacyRecord(row["ipfs"]):
            hash_display = "[LEGACY] " + row["ipfs"]

        locked, lock_status = getRecordPrescriptionStatus(row["record_id"])

        output += "<tr><td>" + formatId("record", row["record_id"]) + "</td>"
        output += "<td>" + formatId("patient", row["patient_id"]) + "</td>"
        output += "<td>" + row["patient_name"] + "</td>"
        output += "<td>" + hash_display + "</td>"
        output += "<td>" + row["record_type"] + "</td>"
        output += "<td>" + formatLocalTime(row["timestamp"]) + "</td>"
        output += "<td>" + lock_status + "</td>"
        output += "<td>" + recordContentDownloadCell(row["record_id"], row["ipfs"]) + "</td>"
        output += "<td>" + prescriptionSubmitCell(row["record_id"], row["patient_id"], locked) + "</td></tr>"

    output += "</table>"
    return output


def downloadButton(url):
    return "<a href='" + url + "' class='btn btn-primary btn-sm'>Download</a>"


@app.route("/DownloadRecord/<record_id>")
def DownloadRecord(record_id):
    global blockchain_tx_count
    role = session.get("role")
    if role not in ("patient", "doctor"):
        return render_template("index.html", msg="Please login to download records")

    web3, contract, account = getContract()
    record_id_int = parseId(record_id)
    record_patient_id = contract.functions.getRecordPatientId(record_id_int).call()
    ipfs_hash = contract.functions.getRecordIpfsHash(record_id_int).call()
    filename = contract.functions.getRecordFileName(record_id_int).call()
    if filename == "":
        record_type = contract.functions.getRecordType(record_id_int).call()
        safe_type = str(record_type).replace(" ", "_")
        filename = "record_" + str(record_id) + "_" + safe_type + ".dat"

    if role == "patient":
        err = mustBeRole("patient", "PatientLogin.html")
        if err:
            return err
        if str(session.get("user_id", "")) != str(record_patient_id):
            return render_template("index.html", msg="You are not allowed to download this record")

    if role == "doctor":
        err = mustBeRole("doctor", "DoctorLogin.html")
        if err:
            return err
        doctor_id = session.get("user_id", 0)
        authorized = contract.functions.isDoctorAuthorized(int(doctor_id), record_id_int).call()
        if not authorized:
            return render_template("index.html", msg="You are not allowed to download this record")

        if str(record_id_int) not in session.get("accessed_records", []):
            msg = contract.functions.accessSharedRecord(doctor_id, record_id_int).transact({"from": account})
            web3.eth.wait_for_transaction_receipt(msg)
            if "accessed_records" not in session:
                session["accessed_records"] = []
            session["accessed_records"].append(str(record_id_int))
            session.modified = True
            blockchain_tx_count += 1

    file_bytes = getDecryptedFileBytes(ipfs_hash, record_timing=True)
    return makeDownloadResponse(file_bytes, filename)


@app.route("/DownloadPrescription/<prescription_id>")
def DownloadPrescription(prescription_id):
    role = session.get("role")
    if role not in ("patient", "doctor"):
        return render_template("index.html", msg="Please login to download prescriptions")

    _, contract, _ = getContract()
    prescription_id_int = parseId(prescription_id)
    pres = contract.functions.prescriptionList(prescription_id_int).call()
    patient_id = pres[0]
    doctor_id = pres[1]
    ipfs_hash = pres[3]
    filename = pres[4]
    if filename == "":
        filename = "prescription_" + str(prescription_id) + ".dat"

    if role == "patient":
        err = mustBeRole("patient", "PatientLogin.html")
        if err:
            return err
        if str(session.get("user_id", "")) != str(patient_id):
            return render_template("index.html", msg="You are not allowed to download this prescription")
        if str(prescription_id_int) not in session.get("viewed_prescriptions", []):
            logPrescriptionView(prescription_id_int, int(patient_id))
            if "viewed_prescriptions" not in session:
                session["viewed_prescriptions"] = []
            session["viewed_prescriptions"].append(str(prescription_id_int))
            session.modified = True

    if role == "doctor":
        err = mustBeRole("doctor", "DoctorLogin.html")
        if err:
            return err
        if str(session.get("user_id", "")) != str(doctor_id):
            return render_template("index.html", msg="You are not allowed to download this prescription")
        if str(prescription_id_int) not in session.get("viewed_prescriptions", []):
            logPrescriptionView(prescription_id_int, int(doctor_id))
            if "viewed_prescriptions" not in session:
                session["viewed_prescriptions"] = []
            session["viewed_prescriptions"].append(str(prescription_id_int))
            session.modified = True

    file_bytes = getDecryptedFileBytes(ipfs_hash, record_timing=True)
    return makeDownloadResponse(file_bytes, filename)


@app.route("/")
def home():
    return render_template("index.html", msg="")


@app.route("/logout")
def logout():
    session.clear()
    return render_template("index.html", msg="Logged out successfully")


@app.route("/AdminLogin", methods=["GET", "POST"])
def AdminLogin():
    if request.method == "GET":
        return render_template("AdminLogin.html", msg="")


@app.route("/AdminLoginAction", methods=["POST"])
def AdminLoginAction():
    if request.method == "POST":
        username = request.form["t1"]
        password = request.form["t2"]
        password_hash = hashPassword(password)

        web3, contract, account = getContract()
        admin_count = contract.functions.adminCount().call()

        if admin_count == 0 and username == "admin" and password == "admin":
            data = username + "#" + password_hash
            saveDataBlockChain(data, "admin")
            session["role"] = "admin"
            session["user_id"] = 0
            session["username"] = username
            return render_template("AdminScreen.html", msg="Welcome " + username)

        status, user_id = checkLogin(username, password, "admin")
        if status == "success":
            session["role"] = "admin"
            session["user_id"] = user_id
            session["username"] = username
            return render_template("AdminScreen.html", msg="Welcome " + username)

        return render_template("AdminLogin.html", msg="Invalid username or password")


@app.route("/AdminScreen", methods=["GET"])
def AdminScreen():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    return render_template("AdminScreen.html", msg="Admin Dashboard")


@app.route("/CreateOrganization", methods=["GET"])
def CreateOrganization():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    return render_template("CreateOrganization.html", msg="")


@app.route("/CreateOrganizationAction", methods=["POST"])
def CreateOrganizationAction():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    if request.method == "POST":
        name = request.form["t1"]
        address = request.form["t2"]
        contact = request.form["t3"]
        data = name + "#" + address + "#" + contact
        saveDataBlockChain(data, "organization")
        web3, contract, account = getContract()
        org_id = contract.functions.organizationCount().call() - 1
        return render_template(
            "CreateOrganization.html",
            msg="Organization saved to blockchain. Organization ID: " + formatId("organization", org_id),
        )


@app.route("/RegisterDoctor", methods=["GET"])
def RegisterDoctor():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    readDetails("organization")
    org_options = ""
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        org_options += (
            "<option value='"
            + row[0]
            + "'>"
            + formatId("organization", row[0])
            + " - "
            + row[1]
            + "</option>"
        )
    return render_template("RegisterDoctor.html", msg="", options=org_options)


@app.route("/RegisterDoctorAction", methods=["POST"])
def RegisterDoctorAction():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    if request.method == "POST":
        name = request.form["t1"]
        spec = request.form["t2"]
        org_id = request.form["t3"]
        username = request.form["t4"]
        password = hashPassword(request.form["t5"])

        readDetails("doctor")
        arr = details.split("\n")
        for i in range(len(arr) - 1):
            row = arr[i].split("#")
            if row[4] == username:
                readDetails("organization")
                org_options = ""
                org_arr = details.split("\n")
                for j in range(len(org_arr) - 1):
                    org_row = org_arr[j].split("#")
                    org_options += (
                        "<option value='"
                        + org_row[0]
                        + "'>"
                        + formatId("organization", org_row[0])
                        + " - "
                        + org_row[1]
                        + "</option>"
                    )
                return render_template("RegisterDoctor.html", msg="Username already exists", options=org_options)

        data = name + "#" + spec + "#" + org_id + "#" + username + "#" + password
        saveDataBlockChain(data, "doctor")
        web3, contract, account = getContract()
        doctor_id = contract.functions.doctorCount().call() - 1
        return render_template(
            "RegisterDoctor.html",
            msg="Doctor registered successfully. Login with username: "
            + username
            + " and password. Doctor ID: "
            + formatId("doctor", doctor_id),
            options="",
        )


@app.route("/ViewOrganizations", methods=["GET"])
def ViewOrganizations():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ["Org ID", "Name", "Address", "Contact"]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    readDetails("organization")
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        output += "<tr><td>" + formatId("organization", row[0]) + "</td>"
        output += "<td>" + row[1] + "</td>"
        output += "<td>" + row[2] + "</td>"
        output += "<td>" + row[3] + "</td></tr>"

    output += "</table>"
    return render_template("ViewOrganizations.html", msg=output)


@app.route("/ViewDoctors", methods=["GET"])
def ViewDoctors():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ["Doctor ID", "Name", "Specialization", "Organization ID", "Username"]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    readDetails("doctor")
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        output += "<tr><td>" + formatId("doctor", row[0]) + "</td>"
        output += "<td>" + row[1] + "</td>"
        output += "<td>" + row[2] + "</td>"
        output += "<td>" + formatId("organization", row[3]) + "</td>"
        output += "<td>" + row[4] + "</td></tr>"

    output += "</table>"
    return render_template("ViewDoctors.html", msg=output)


@app.route("/ViewPatients", methods=["GET"])
def ViewPatients():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ["Patient ID", "Name", "Gender", "DOB", "Contact", "Address", "Username"]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    readDetails("patient")
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        output += "<tr><td>" + formatId("patient", row[0]) + "</td>"
        output += "<td>" + row[1] + "</td>"
        output += "<td>" + row[2] + "</td>"
        output += "<td>" + row[3] + "</td>"
        output += "<td>" + row[4] + "</td>"
        output += "<td>" + row[5] + "</td>"
        output += "<td>" + row[6] + "</td></tr>"

    output += "</table>"
    return render_template("ViewPatients.html", msg=output)


@app.route("/PatientRegister", methods=["GET"])
def PatientRegister():
    return render_template("PatientRegister.html", msg="")


@app.route("/PatientRegisterAction", methods=["POST"])
def PatientRegisterAction():
    if request.method == "POST":
        name = request.form["t1"]
        gender = request.form["t2"]
        dob = request.form["t3"]
        contact = request.form["t4"]
        address = request.form["t5"]
        username = request.form["t6"]
        password = hashPassword(request.form["t7"])

        readDetails("patient")
        arr = details.split("\n")
        for i in range(len(arr) - 1):
            row = arr[i].split("#")
            if row[6] == username:
                return render_template("PatientRegister.html", msg="Username already exists")

        data = name + "#" + gender + "#" + dob + "#" + contact + "#" + address + "#" + username + "#" + password
        saveDataBlockChain(data, "patient")
        web3, contract, account = getContract()
        patient_id = contract.functions.patientCount().call() - 1
        return render_template(
            "PatientRegister.html",
            msg="Registration successful. Login with username: "
            + username
            + " and your password. Patient ID: "
            + formatId("patient", patient_id),
        )


@app.route("/PatientLogin", methods=["GET"])
def PatientLogin():
    return render_template("PatientLogin.html", msg="")


@app.route("/PatientLoginAction", methods=["POST"])
def PatientLoginAction():
    if request.method == "POST":
        username = request.form["t1"]
        password = request.form["t2"]
        if isFormattedId(username):
            return render_template(
                "PatientLogin.html",
                msg="Please login with username and password, not Patient ID",
            )
        status, user_id = checkLogin(username, password, "patient")
        if status == "success":
            session["role"] = "patient"
            session["user_id"] = user_id
            session["username"] = username
            return render_template(
                "PatientScreen.html",
                msg="Welcome, " + username,
            )
        return render_template("PatientLogin.html", msg="Invalid username or password")


@app.route("/PatientScreen", methods=["GET"])
def PatientScreen():
    err = mustBeRole("patient", "PatientLogin.html")
    if err:
        return err
    username = session.get("username", "")
    msg = "Patient Dashboard"
    if username != "":
        msg = "Patient Dashboard | Logged in as: " + username
    return render_template("PatientScreen.html", msg=msg)


@app.route("/DoctorLogin", methods=["GET"])
def DoctorLogin():
    return render_template("DoctorLogin.html", msg="")


@app.route("/DoctorLoginAction", methods=["POST"])
def DoctorLoginAction():
    if request.method == "POST":
        username = request.form["t1"]
        password = request.form["t2"]
        if isFormattedId(username):
            return render_template(
                "DoctorLogin.html",
                msg="Please login with username and password, not Doctor ID",
            )
        status, user_id = checkLogin(username, password, "doctor")
        if status == "success":
            session["role"] = "doctor"
            session["user_id"] = user_id
            session["username"] = username
            return render_template(
                "DoctorScreen.html",
                msg="Welcome, " + username,
            )
        return render_template("DoctorLogin.html", msg="Invalid username or password")


@app.route("/DoctorScreen", methods=["GET"])
def DoctorScreen():
    err = mustBeRole("doctor", "DoctorLogin.html")
    if err:
        return err
    username = session.get("username", "")
    msg = "Doctor Dashboard"
    if username != "":
        msg = "Doctor Dashboard | Logged in as: " + username
    return render_template("DoctorScreen.html", msg=msg)


@app.route("/UploadRecord", methods=["GET"])
def UploadRecord():
    if "user_id" not in session or session.get("role") != "patient":
        return render_template(
            "UploadRecord.html",
            msg="Please login as patient first",
            username="",
            patient_id="",
            options="",
        )

    patient_id = session["user_id"]
    org_options = getOrganizationOptions()
    return render_template(
        "UploadRecord.html",
        msg="",
        username=session.get("username", ""),
        patient_id=formatId("patient", patient_id),
        options=org_options,
    )


@app.route("/UploadRecordAction", methods=["POST"])
def UploadRecordAction():
    if request.method == "POST":
        patient_id = session.get("user_id", "")
        org_options = getOrganizationOptions()

        if session.get("role") != "patient":
            return render_template(
                "UploadRecord.html",
                msg="Please login as patient first",
                username=session.get("username", ""),
                patient_id=formatId("patient", patient_id) if patient_id != "" else "",
                options=org_options,
            )

        record_type = request.form["t1"]
        record_text = request.form.get("t3", "")
        file = request.files.get("t2")
        org_ids = request.form.getlist("t4")

        if file and file.filename:
            raw_data = file.read()
            original_filename = file.filename
        elif record_text.strip() != "":
            raw_data = record_text.encode("utf-8")
            original_filename = "record_text.txt"
        else:
            return render_template(
                "UploadRecord.html",
                msg="Please upload a file or enter text",
                username=session.get("username", ""),
                patient_id=formatId("patient", patient_id),
                options=org_options,
            )

        if len(org_ids) == 0:
            return render_template(
                "UploadRecord.html",
                msg="Please select at least one organization to share with",
                username=session.get("username", ""),
                patient_id=formatId("patient", patient_id),
                options=org_options,
            )

        encrypted_data = doubleEncrypt(raw_data)
        ipfs_hash = uploadToPinata(encrypted_data, "encrypted_record.b64")
        data = str(patient_id) + "#" + ipfs_hash + "#" + record_type + "#" + original_filename
        saveDataBlockChain(data, "record")

        web3, contract, account = getContract()
        record_id = contract.functions.recordCount().call() - 1

        for org_id in org_ids:
            share_data = str(record_id) + "#" + str(patient_id) + "#" + org_id
            saveDataBlockChain(share_data, "sharing")

        return render_template(
            "UploadRecord.html",
            msg="Record uploaded successfully. Record ID: "
            + formatId("record", record_id)
            + " | Shared with selected organizations",
            username=session.get("username", ""),
            patient_id=formatId("patient", patient_id),
            options=org_options,
        )


@app.route("/ViewMyRecords", methods=["GET"])
def ViewMyRecords():
    err = mustBeRole("patient", "PatientLogin.html")
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = [
        "Record ID",
        "Patient ID",
        "IPFS Hash",
        "Record Type",
        "Uploaded At",
        "Shared With",
        "Prescription Status",
        "Content / Download",
        "Manage Sharing",
    ]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    patient_id = str(session.get("user_id", ""))
    readDetails("record")
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        if row[1] == patient_id:
            hash_display = row[2]
            if isLegacyRecord(row[2]):
                hash_display = "[LEGACY] " + row[2]

            _, lock_status = getRecordPrescriptionStatus(row[0])
            shared_orgs = getRecordSharedOrganizations(row[0])
            if len(shared_orgs) == 0:
                shared_text = "None"
            else:
                shared_text = ", ".join([org["org_name"] for org in shared_orgs])

            output += "<tr><td>" + formatId("record", row[0]) + "</td>"
            output += "<td>" + formatId("patient", row[1]) + "</td>"
            output += "<td>" + hash_display + "</td>"
            output += "<td>" + row[3] + "</td>"
            output += "<td>" + formatLocalTime(row[4]) + "</td>"
            output += "<td>" + shared_text + "</td>"
            output += "<td>" + lock_status + "</td>"
            file_name = row[6] if len(row) > 6 else ""
            output += "<td>" + recordContentDownloadCell(row[0], row[2], file_name) + "</td>"
            output += (
                "<td><a href='/ManageRecordSharing/"
                + formatId("record", row[0])
                + "' class='btn btn-warning btn-sm'>Manage</a></td></tr>"
            )

    output += "</table>"
    return render_template(
        "ViewMyRecords.html",
        page_title="My Medical Records",
        status_msg="",
        msg=output,
    )


@app.route("/ManageRecordSharing/<record_id>", methods=["GET"])
def ManageRecordSharing(record_id):
    err = mustBeRole("patient", "PatientLogin.html")
    if err:
        return err
    patient_id = str(session.get("user_id", ""))
    _, contract, _ = getContract()
    record_id_int = parseId(record_id)
    record_patient_id = contract.functions.getRecordPatientId(record_id_int).call()
    if str(record_patient_id) != patient_id:
        return render_template(
            "ViewMyRecords.html",
            page_title="My Medical Records",
            status_msg="<div class='alert alert-danger'>You are not allowed to manage this record</div>",
            msg="",
        )
    return render_template(
        "ViewMyRecords.html",
        page_title="Manage Record Sharing",
        status_msg="",
        msg=buildManageSharingPage(record_id_int, patient_id),
    )


@app.route("/ShareRecordAction", methods=["POST"])
def ShareRecordAction():
    err = mustBeRole("patient", "PatientLogin.html")
    if err:
        return err
    record_id = parseId(request.form["t1"])
    org_ids = request.form.getlist("t2")
    patient_id = str(session.get("user_id", ""))
    if len(org_ids) == 0:
        status_msg = "Please select at least one organization"
        alert_class = "alert-danger"
    else:
        for org_id in org_ids:
            share_data = str(record_id) + "#" + patient_id + "#" + org_id
            saveDataBlockChain(share_data, "sharing")
        status_msg = "Record shared with selected organizations successfully"
        alert_class = "alert-info"
    return render_template(
        "ViewMyRecords.html",
        page_title="Manage Record Sharing",
        status_msg="<div class='alert " + alert_class + "'>" + status_msg + "</div>",
        msg=buildManageSharingPage(record_id, patient_id),
    )


@app.route("/RevokeShareAction", methods=["POST"])
def RevokeShareAction():
    err = mustBeRole("patient", "PatientLogin.html")
    if err:
        return err
    record_id = parseId(request.form["t1"])
    org_id = request.form["t2"]
    patient_id = str(session.get("user_id", ""))
    revoke_data = str(record_id) + "#" + patient_id + "#" + org_id
    saveDataBlockChain(revoke_data, "revoke_share")
    return render_template(
        "ViewMyRecords.html",
        page_title="Manage Record Sharing",
        status_msg="<div class='alert alert-info'>Sharing revoked successfully</div>",
        msg=buildManageSharingPage(record_id, patient_id),
    )


@app.route("/ViewSharedRecords", methods=["GET"])
def ViewSharedRecords():
    err = mustBeRole("doctor", "DoctorLogin.html")
    if err:
        return err
    doctor_id = session.get("user_id", 0)
    filters = {
        "patient_name": request.args.get("f_patient", "").strip(),
        "record_type": request.args.get("f_type", "").strip(),
        "status": request.args.get("f_status", "").strip(),
    }
    status_msg = request.args.get("status_msg", "")
    return render_template(
        "ViewSharedRecords.html",
        msg=buildSharedRecordsTable(doctor_id, filters),
        f_patient=filters["patient_name"],
        f_type=filters["record_type"],
        f_status=filters["status"],
        status_msg=status_msg,
    )


@app.route("/ViewPatientHistory", methods=["GET"])
def ViewPatientHistory():
    err = mustBeRole("doctor", "DoctorLogin.html")
    if err:
        return err

    output = ""
    doctor_id = session.get("user_id", 0)
    shared_records = getDoctorSharedRecords(doctor_id)

    patients = {}
    for row in shared_records:
        patient_id = row["patient_id"]
        if patient_id not in patients:
            patients[patient_id] = {"name": row["patient_name"], "records": []}
        patients[patient_id]["records"].append(row)

    for patient_id in sorted(patients.keys()):
        patient_name = patients[patient_id]["name"]
        output += (
            "<h4 class='mt-3'>Patient: "
            + patient_name
            + " (ID: "
            + formatId("patient", patient_id)
            + ")</h4>"
        )
        output += "<table class='" + TABLE_CLASS + "'>"
        output += "<tr><th>Record ID</th><th>Type</th><th>Uploaded At</th><th>Prescription Status</th><th>Content / Download</th><th>Submit Prescription</th></tr>"
        for row in patients[patient_id]["records"]:
            locked, lock_status = getRecordPrescriptionStatus(row["record_id"])
            output += "<tr><td>" + formatId("record", row["record_id"]) + "</td>"
            output += "<td>" + row["record_type"] + "</td>"
            output += "<td>" + formatLocalTime(row["timestamp"]) + "</td>"
            output += "<td>" + lock_status + "</td>"
            output += "<td>" + recordContentDownloadCell(row["record_id"], row["ipfs"]) + "</td>"
            output += "<td>" + prescriptionSubmitCell(row["record_id"], row["patient_id"], locked) + "</td></tr>"
        output += "</table><br/>"

    if output == "":
        output = "No shared patient history found"

    return render_template("ViewPatientHistory.html", msg=output)


@app.route("/SubmitPrescription/<record_id>/<patient_id>", methods=["GET"])
def SubmitPrescription(record_id, patient_id):
    err = mustBeRole("doctor", "DoctorLogin.html")
    if err:
        return err
    doctor_id = session.get("user_id", 0)
    _, contract, _ = getContract()
    record_id_int = parseId(record_id)
    patient_id_int = parseId(patient_id)
    authorized = contract.functions.isDoctorAuthorized(int(doctor_id), record_id_int).call()
    if not authorized:
        return render_template(
            "ViewSharedRecords.html",
            msg=buildSharedRecordsTable(doctor_id),
            status_msg="You are not authorized for this record",
            f_patient="",
            f_type="",
            f_status="",
        )

    locked = contract.functions.isRecordLocked(record_id_int).call()
    if locked:
        return render_template(
            "ViewSharedRecords.html",
            msg=buildSharedRecordsTable(doctor_id),
            status_msg="Prescription already submitted for this record",
            f_patient="",
            f_type="",
            f_status="",
        )

    return renderPrescriptionForm(record_id_int, patient_id_int)


@app.route("/SubmitPrescriptionAction", methods=["POST"])
def SubmitPrescriptionAction():
    err = mustBeRole("doctor", "DoctorLogin.html")
    if err:
        return err
    if request.method == "POST":
        selected = request.form["t1"]
        prescription_text = request.form.get("t3", "")
        file = request.files.get("t2")
        doctor_id = session.get("user_id", 0)
        table = buildSharedRecordsTable(doctor_id)

        if selected == "" or "#" not in selected:
            return render_template(
                "ViewSharedRecords.html",
                msg=table,
                status_msg="Invalid record selected",
                f_patient="",
                f_type="",
                f_status="",
            )

        record_part, patient_part = selected.split("#")
        record_id = parseId(record_part)
        patient_id = parseId(patient_part)

        if file and file.filename:
            raw_data = file.read()
            original_filename = file.filename
        elif prescription_text.strip() != "":
            raw_data = prescription_text.encode("utf-8")
            original_filename = "prescription_text.txt"
        else:
            return renderPrescriptionForm(
                record_id,
                patient_id,
                msg="Please upload a file or enter prescription text",
            )

        web3, contract, account = getContract()
        authorized = contract.functions.isDoctorAuthorized(int(doctor_id), int(record_id)).call()
        if not authorized:
            return render_template(
                "ViewSharedRecords.html",
                msg=table,
                status_msg="You are not authorized for this record",
                f_patient="",
                f_type="",
                f_status="",
            )

        locked = contract.functions.isRecordLocked(int(record_id)).call()
        if locked:
            return render_template(
                "ViewSharedRecords.html",
                msg=table,
                status_msg="Prescription already submitted for this record",
                f_patient="",
                f_type="",
                f_status="",
            )

        encrypted_data = doubleEncrypt(raw_data)
        ipfs_hash = uploadToPinata(encrypted_data, "encrypted_prescription.b64")
        data = (
            str(doctor_id)
            + "#"
            + str(patient_id)
            + "#"
            + str(record_id)
            + "#"
            + ipfs_hash
            + "#"
            + original_filename
        )
        saveDataBlockChain(data, "prescription")
        table = buildSharedRecordsTable(doctor_id)
        return render_template(
            "ViewSharedRecords.html",
            msg=table,
            status_msg="Prescription submitted for Record ID "
            + formatId("record", record_id)
            + " and Patient ID "
            + formatId("patient", patient_id),
            f_patient="",
            f_type="",
            f_status="",
        )


@app.route("/ViewPatientPrescription", methods=["GET"])
def ViewPatientPrescription():
    err = mustBeRole("patient", "PatientLogin.html")
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ["Prescription ID", "Doctor ID", "Record ID", "IPFS Hash", "Submitted At", "Status", "Content / Download"]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    patient_id = str(session.get("user_id", ""))
    readDetails("prescription")
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        if row[1] == patient_id:
            hash_display = row[4]
            if isLegacyRecord(row[4]):
                hash_display = "[LEGACY] " + row[4]

            output += "<tr><td>" + formatId("prescription", row[0]) + "</td>"
            output += "<td>" + formatId("doctor", row[2]) + "</td>"
            output += "<td>" + formatId("record", row[3]) + "</td>"
            output += "<td>" + hash_display + "</td>"
            output += "<td>" + formatLocalTime(row[6]) + "</td>"
            output += "<td>" + row[7] + "</td>"
            output += "<td>" + prescriptionContentDownloadCell(row[0], row[4], row[5]) + "</td></tr>"

    output += "</table>"
    return render_template("ViewPrescription.html", msg=output, back_link="/PatientScreen")


@app.route("/ViewDoctorPrescription", methods=["GET"])
def ViewDoctorPrescription():
    err = mustBeRole("doctor", "DoctorLogin.html")
    if err:
        return err
    output = "<table class='" + TABLE_CLASS + "'>"
    headers = ["Prescription ID", "Patient ID", "Record ID", "IPFS Hash", "Submitted At", "Status", "Content / Download"]
    output += "<tr>"
    for header in headers:
        output += "<th>" + header + "</th>"
    output += "</tr>"

    doctor_id = str(session.get("user_id", ""))
    readDetails("prescription")
    arr = details.split("\n")
    for i in range(len(arr) - 1):
        row = arr[i].split("#")
        if row[2] == doctor_id:
            hash_display = row[4]
            if isLegacyRecord(row[4]):
                hash_display = "[LEGACY] " + row[4]

            output += "<tr><td>" + formatId("prescription", row[0]) + "</td>"
            output += "<td>" + formatId("patient", row[1]) + "</td>"
            output += "<td>" + formatId("record", row[3]) + "</td>"
            output += "<td>" + hash_display + "</td>"
            output += "<td>" + formatLocalTime(row[6]) + "</td>"
            output += "<td>" + row[7] + "</td>"
            output += "<td>" + prescriptionContentDownloadCell(row[0], row[4], row[5]) + "</td></tr>"

    output += "</table>"
    return render_template("ViewPrescription.html", msg=output, back_link="/DoctorScreen")


@app.route("/AuditLogs", methods=["GET"])
def AuditLogs():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err

    patient_names = {}
    doctor_names = {}
    org_names = {}
    readDetails("patient")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        patient_names[parts[0]] = parts[1]
    readDetails("doctor")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        doctor_names[parts[0]] = parts[1]
    readDetails("organization")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        org_names[parts[0]] = parts[1]

    output = "<h4 class='mt-2'>Organization Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Org ID</th><th>Name</th><th>Address</th><th>Contact</th></tr>"
    readDetails("organization")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        output += (
            "<tr><td>"
            + formatId("organization", parts[0])
            + "</td><td>"
            + parts[1]
            + "</td><td>"
            + parts[2]
            + "</td><td>"
            + parts[3]
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Doctor Registration Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Doctor ID</th><th>Name</th><th>Organization</th><th>Username</th></tr>"
    readDetails("doctor")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        org_name = org_names.get(parts[3], parts[3])
        output += (
            "<tr><td>"
            + formatId("doctor", parts[0])
            + "</td><td>"
            + parts[1]
            + "</td><td>"
            + org_name
            + " ("
            + formatId("organization", parts[3])
            + ")</td><td>"
            + parts[4]
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Patient Registration Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Patient ID</th><th>Name</th><th>Username</th></tr>"
    readDetails("patient")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        output += (
            "<tr><td>"
            + formatId("patient", parts[0])
            + "</td><td>"
            + parts[1]
            + "</td><td>"
            + parts[6]
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Medical Record Upload Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Record ID</th><th>Patient</th><th>IPFS Hash</th><th>Type</th><th>File Name</th></tr>"
    readDetails("record")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        patient_name = patient_names.get(parts[1], parts[1])
        file_name = parts[6] if len(parts) > 6 else ""
        output += (
            "<tr><td>"
            + formatId("record", parts[0])
            + "</td><td>"
            + patient_name
            + " ("
            + formatId("patient", parts[1])
            + ")</td><td>"
            + parts[2]
            + "</td><td>"
            + parts[3]
            + "</td><td>"
            + file_name
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Record Sharing Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Sharing ID</th><th>Record ID</th><th>Patient</th><th>Organization</th><th>Shared At</th></tr>"
    readDetails("sharing")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        patient_name = patient_names.get(parts[2], parts[2])
        org_name = org_names.get(parts[3], parts[3])
        output += (
            "<tr><td>"
            + formatId("sharing", parts[0])
            + "</td><td>"
            + formatId("record", parts[1])
            + "</td><td>"
            + patient_name
            + " ("
            + formatId("patient", parts[2])
            + ")</td><td>"
            + org_name
            + " ("
            + formatId("organization", parts[3])
            + ")</td><td>"
            + formatLocalTime(parts[4])
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Prescription Submission Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Prescription ID</th><th>Patient</th><th>Doctor</th><th>Record ID</th><th>Submitted At</th><th>Status</th></tr>"
    readDetails("prescription")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        patient_name = patient_names.get(parts[1], parts[1])
        doctor_name = doctor_names.get(parts[2], parts[2])
        output += (
            "<tr><td>"
            + formatId("prescription", parts[0])
            + "</td><td>"
            + patient_name
            + " ("
            + formatId("patient", parts[1])
            + ")</td><td>"
            + doctor_name
            + " ("
            + formatId("doctor", parts[2])
            + ")</td><td>"
            + formatId("record", parts[3])
            + "</td><td>"
            + formatLocalTime(parts[6])
            + "</td><td>"
            + parts[7]
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Record Access Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Access ID</th><th>Doctor</th><th>Record ID</th><th>Patient</th><th>Organization</th><th>Accessed At</th></tr>"
    readDetails("access")
    for row in details.split("\n")[:-1]:
        parts = row.split("#")
        doctor_name = doctor_names.get(parts[1], parts[1])
        patient_name = patient_names.get(parts[3], parts[3])
        org_name = org_names.get(parts[4], parts[4])
        output += (
            "<tr><td>"
            + formatId("access", parts[0])
            + "</td><td>"
            + doctor_name
            + " ("
            + formatId("doctor", parts[1])
            + ")</td><td>"
            + formatId("record", parts[2])
            + "</td><td>"
            + patient_name
            + " ("
            + formatId("patient", parts[3])
            + ")</td><td>"
            + org_name
            + " ("
            + formatId("organization", parts[4])
            + ")</td><td>"
            + formatLocalTime(parts[5])
            + "</td></tr>"
        )
    output += "</table>"

    output += "<h4 class='mt-4'>Prescription View Logs</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Prescription ID</th><th>Viewer</th><th>Patient</th><th>Doctor</th><th>Record ID</th></tr>"
    view_logs = getPrescriptionViewLogs()
    if len(view_logs) == 0:
        output += "<tr><td colspan='5'>No prescription view logs yet</td></tr>"
    for log in view_logs:
        output += "<tr><td>" + log["prescription_id"] + "</td><td>" + log["viewer_name"] + " (" + log["viewer_id"] + ")</td><td>" + log["patient_name"] + "</td><td>" + log["doctor_name"] + "</td><td>" + log["record_id"] + "</td></tr>"
    output += "</table>"

    return render_template("AuditLogs.html", msg=output)


@app.route("/Analytics", methods=["GET"])
def Analytics():
    err = mustBeRole("admin", "AdminLogin.html")
    if err:
        return err

    readDetails("analytics")
    row = details.split("#")
    labels = ["Organizations", "Doctors", "Patients", "Records", "Sharings", "Prescriptions", "Access Logs"]
    values = [int(row[i]) for i in range(7)]

    output = "<h4>Summary</h4><table class='" + TABLE_CLASS + "'>"
    output += "<tr><th>Metric</th><th>Count</th></tr>"
    for i in range(len(labels)):
        output += "<tr><td>" + labels[i] + "</td><td>" + str(values[i]) + "</td></tr>"
    avg_encrypt = float(row[7]) if row[7] else 0
    avg_decrypt = float(row[8]) if row[8] else 0
    time_diff = round(abs(avg_encrypt - avg_decrypt), 2)
    if avg_encrypt > avg_decrypt:
        time_compare = "Encryption is slower than decryption by " + str(time_diff) + " ms"
    elif avg_decrypt > avg_encrypt:
        time_compare = "Decryption is slower than encryption by " + str(time_diff) + " ms"
    else:
        time_compare = "Encryption and decryption times are equal"

    output += "<tr><td>Blockchain Transactions (session)</td><td>" + row[9] + "</td></tr>"
    output += "</table>"



    org_names = {}
    readDetails("organization")
    for org_row in details.split("\n")[:-1]:
        parts = org_row.split("#")
        org_names[parts[0]] = parts[1]

    _, contract, _ = getContract()
    org_share_labels = []
    org_share_values = []
    readDetails("record")
    record_arr = details.split("\n")[:-1]
    for org_id in sorted(org_names.keys()):
        active_count = 0
        for rec in record_arr:
            rec_parts = rec.split("#")
            if contract.functions.isRecordSharedWithOrg(int(rec_parts[0]), int(org_id)).call():
                active_count += 1
        if active_count > 0:
            org_share_labels.append(org_names[org_id])
            org_share_values.append(active_count)

    doctor_names = {}
    readDetails("doctor")
    for doc_row in details.split("\n")[:-1]:
        parts = doc_row.split("#")
        doctor_names[parts[0]] = parts[1]

    doctor_pres_labels = []
    doctor_pres_values = []
    readDetails("prescription")
    doctor_pres_count = {}
    for pres_row in details.split("\n")[:-1]:
        parts = pres_row.split("#")
        doctor_id = parts[2]
        if doctor_id not in doctor_pres_count:
            doctor_pres_count[doctor_id] = 0
        doctor_pres_count[doctor_id] += 1
    for doctor_id in sorted(doctor_pres_count.keys()):
        doctor_pres_labels.append(doctor_names.get(doctor_id, "Doctor " + doctor_id))
        doctor_pres_values.append(doctor_pres_count[doctor_id])



    chart_summary = json.dumps({"labels": labels, "values": values})
    chart_share = json.dumps({"labels": org_share_labels, "values": org_share_values})
    chart_doctor = json.dumps({"labels": doctor_pres_labels, "values": doctor_pres_values})
    
    run_labels = [f"Run {i+1}" for i in range(max(len(encryption_times), len(decryption_times)))]
    chart_encrypt = json.dumps({
        "labels": run_labels,
        "encryption": encryption_times,
        "decryption": decryption_times
    })

    return render_template(
        "Analytics.html",
        msg=output,
        chart_summary=chart_summary,
        chart_share=chart_share,
        chart_doctor=chart_doctor,
        chart_encrypt=chart_encrypt,
    )


loadOrCreateKeys()

if __name__ == "__main__":
    app.run(debug=False)
