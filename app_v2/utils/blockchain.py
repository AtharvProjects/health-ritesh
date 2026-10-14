import json
from web3 import Web3, HTTPProvider
from app_v2.config import Config, AppState

def getContract():
    web3 = Web3(HTTPProvider(Config.BLOCKCHAIN_ADDRESS))
    accounts = web3.eth.accounts
    if len(accounts) == 0:
        raise Exception("Ganache is not running or no accounts found")
    account = accounts[0]
    with open(Config.COMPILED_CONTRACT_PATH) as file:
        contract_json = json.load(file)
        contract_abi = contract_json["abi"]
    contract = web3.eth.contract(address=Config.DEPLOYED_CONTRACT_ADDRESS, abi=contract_abi)
    return web3, contract, account

def readDetails(contract_type):
    AppState.details = ""
    web3, contract, account = getContract()

    if contract_type == "admin":
        count = contract.functions.adminCount().call()
        for i in range(count):
            username = contract.functions.getAdminUsername(i).call()
            password = contract.functions.getAdminPasswordHash(i).call()
            AppState.details += str(username) + "#" + str(password) + "\n"

    elif contract_type == "organization":
        count = contract.functions.organizationCount().call()
        for i in range(count):
            name = contract.functions.getOrganizationName(i).call()
            address = contract.functions.getOrganizationAddress(i).call()
            contact = contract.functions.getOrganizationContact(i).call()
            AppState.details += str(i) + "#" + str(name) + "#" + str(address) + "#" + str(contact) + "\n"

    elif contract_type == "doctor":
        count = contract.functions.doctorCount().call()
        for i in range(count):
            name = contract.functions.getDoctorName(i).call()
            spec = contract.functions.getDoctorSpecialization(i).call()
            org_id = contract.functions.getDoctorOrganizationId(i).call()
            username = contract.functions.getDoctorUsername(i).call()
            password = contract.functions.getDoctorPasswordHash(i).call()
            AppState.details += str(i) + "#" + str(name) + "#" + str(spec) + "#" + str(org_id) + "#" + str(username) + "#" + str(password) + "\n"

    elif contract_type == "patient":
        count = contract.functions.patientCount().call()
        for i in range(count):
            name = contract.functions.getPatientName(i).call()
            gender = contract.functions.getPatientGender(i).call()
            dob = contract.functions.getPatientDob(i).call()
            contact = contract.functions.getPatientContact(i).call()
            address = contract.functions.getPatientAddress(i).call()
            username = contract.functions.getPatientUsername(i).call()
            password = contract.functions.getPatientPasswordHash(i).call()
            AppState.details += str(i) + "#" + str(name) + "#" + str(gender) + "#" + str(dob) + "#" + str(contact) + "#" + str(address) + "#" + str(username) + "#" + str(password) + "\n"

    elif contract_type == "record":
        count = contract.functions.recordCount().call()
        for i in range(count):
            patient_id = contract.functions.getRecordPatientId(i).call()
            ipfs_hash = contract.functions.getRecordIpfsHash(i).call()
            record_type = contract.functions.getRecordType(i).call()
            timestamp = contract.functions.getRecordTimestamp(i).call()
            locked = contract.functions.isRecordLocked(i).call()
            file_name = contract.functions.getRecordFileName(i).call()
            AppState.details += f"{i}#{patient_id}#{ipfs_hash}#{record_type}#{timestamp}#{locked}#{file_name}\n"

    elif contract_type == "sharing":
        count = contract.functions.sharingCount().call()
        for i in range(count):
            record_id = contract.functions.getSharingRecordId(i).call()
            patient_id = contract.functions.getSharingPatientId(i).call()
            org_id = contract.functions.getSharingOrganizationId(i).call()
            shared_time = contract.functions.getSharingTimestamp(i).call()
            AppState.details += f"{i}#{record_id}#{patient_id}#{org_id}#{shared_time}\n"

    elif contract_type == "prescription":
        count = contract.functions.prescriptionCount().call()
        for i in range(count):
            pres = contract.functions.prescriptionList(i).call()
            AppState.details += f"{i}#{pres[0]}#{pres[1]}#{pres[2]}#{pres[3]}#{pres[4]}#{pres[5]}#{pres[6]}\n"

    elif contract_type == "access":
        count = contract.functions.accessCount().call()
        for i in range(count):
            doctor_id = contract.functions.getAccessDoctorId(i).call()
            record_id = contract.functions.getAccessRecordId(i).call()
            patient_id = contract.functions.getAccessPatientId(i).call()
            org_id = contract.functions.getAccessOrganizationId(i).call()
            access_time = contract.functions.getAccessTimestamp(i).call()
            AppState.details += f"{i}#{doctor_id}#{record_id}#{patient_id}#{org_id}#{access_time}\n"

    elif contract_type == "analytics":
        org_count = contract.functions.organizationCount().call()
        doctor_count = contract.functions.doctorCount().call()
        patient_count = contract.functions.patientCount().call()
        record_count = contract.functions.recordCount().call()
        sharing_count = contract.functions.sharingCount().call()
        prescription_count = contract.functions.prescriptionCount().call()
        access_count = contract.functions.accessCount().call()
        avg_encrypt = 0
        avg_decrypt = 0
        if len(AppState.encryption_times) > 0:
            avg_encrypt = round(sum(AppState.encryption_times) / len(AppState.encryption_times), 2)
        if len(AppState.decryption_times) > 0:
            avg_decrypt = round(sum(AppState.decryption_times) / len(AppState.decryption_times), 2)
        AppState.details = f"{org_count}#{doctor_count}#{patient_count}#{record_count}#{sharing_count}#{prescription_count}#{access_count}#{avg_encrypt}#{avg_decrypt}#{AppState.blockchain_tx_count}"

def saveDataBlockChain(currentData, contract_type):
    AppState.details = ""
    web3, contract, account = getContract()
    arr = currentData.split("#")
    tx = {"from": account}

    if contract_type == "admin":
        msg = contract.functions.saveAdmin(arr[0], arr[1]).transact(tx)
    elif contract_type == "organization":
        msg = contract.functions.saveOrganization(arr[0], arr[1], arr[2]).transact(tx)
    elif contract_type == "doctor":
        msg = contract.functions.saveDoctor(arr[0], arr[1], int(arr[2]), arr[3], arr[4]).transact(tx)
    elif contract_type == "patient":
        msg = contract.functions.savePatient(arr[0], arr[1], arr[2], arr[3], arr[4], arr[5], arr[6]).transact(tx)
    elif contract_type == "record":
        msg = contract.functions.saveMedicalRecord(int(arr[0]), arr[1], arr[2], arr[3]).transact(tx)
    elif contract_type == "sharing":
        msg = contract.functions.shareRecord(int(arr[0]), int(arr[1]), int(arr[2])).transact(tx)
    elif contract_type == "revoke_share":
        msg = contract.functions.revokeShare(int(arr[0]), int(arr[1]), int(arr[2])).transact(tx)
    elif contract_type == "prescription":
        msg = contract.functions.savePrescription(int(arr[0]), int(arr[1]), int(arr[2]), arr[3], arr[4]).transact(tx)
    elif contract_type == "prescription_view":
        msg = contract.functions.logPrescriptionViewed(int(arr[0]), int(arr[1])).transact(tx)
    
    web3.eth.wait_for_transaction_receipt(msg)
    AppState.blockchain_tx_count += 1
