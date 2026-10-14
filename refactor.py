import os
import re

app_path = 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We will create a 'core' package
os.makedirs('core', exist_ok=True)
with open('core/__init__.py', 'w', encoding='utf-8') as f:
    f.write('')

# Extract imports
imports_section = re.search(r'^(.*?)\n\napp = Flask\(__name__\)', content, re.DOTALL).group(1)

# globals and settings
globals_code = """import os
from web3 import Web3, HTTPProvider

# Global Settings & States
DETAILS = ""
ENCRYPTION_TIMES = []
DECRYPTION_TIMES = []
BLOCKCHAIN_TX_COUNT = 0
TABLE_CLASS = "table table-bordered table-striped table-hover table-sm"
KEYS_FOLDER = "keys"
os.makedirs(KEYS_FOLDER, exist_ok=True)

# Pinata IPFS keys
PINATA_API_KEY = "1bb8e4d7ff828d8dd537"
PINATA_SECRET_KEY = "b98bfe6db5f5fc1512a7f2060bc24d397aa8765ef49f12eb80463692c80fca29"

# Blockchain settings
BLOCKCHAIN_ADDRESS = "http://127.0.0.1:8545"
COMPILED_CONTRACT_PATH = "build/contracts/HealthcareRecords.json"
DEPLOYED_CONTRACT_ADDRESS = "0x66eEB2f0A61031Fad687409108aAd6AF30148f71"

# Crypto keys
AES_KEY = None
PAILLIER_PUBLIC_KEY = None
PAILLIER_PRIVATE_KEY = None

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
"""
with open('core/config.py', 'w', encoding='utf-8') as f:
    f.write(globals_code)

print("Modularization script generated config.py")
