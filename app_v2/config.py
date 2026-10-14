import os
import json

class Config:
    SECRET_KEY = "healthcare_secret_key"
    KEYS_FOLDER = "keys"
    
    # Pinata IPFS keys - should be moved to .env in production
    PINATA_API_KEY = "1bb8e4d7ff828d8dd537"
    PINATA_SECRET_KEY = "b98bfe6db5f5fc1512a7f2060bc24d397aa8765ef49f12eb80463692c80fca29"
    
    # Blockchain settings
    BLOCKCHAIN_ADDRESS = "http://127.0.0.1:8545"
    COMPILED_CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "..", "build", "contracts", "HealthcareRecords.json")
    
    try:
        with open(COMPILED_CONTRACT_PATH) as _f:
            _net_id = list(json.load(_f)["networks"].keys())[-1]
            _f.seek(0)
            DEPLOYED_CONTRACT_ADDRESS = json.load(_f)["networks"][_net_id]["address"]
    except Exception:
        DEPLOYED_CONTRACT_ADDRESS = "0x345cA3e014Aaf5dcA488057592ee47305D9B3e10"
    
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
    
    TABLE_CLASS = "table table-bordered table-striped table-hover table-sm"

class AppState:
    details = ""
    encryption_times = []
    decryption_times = []
    blockchain_tx_count = 0
    aes_key = None
    paillier_public_key = None
    paillier_private_key = None
