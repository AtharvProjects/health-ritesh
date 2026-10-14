import os
import requests
from app_v2.config import Config
from app_v2.utils.crypto import doubleDecrypt
from app_v2.utils.helpers import isLegacyRecord

def uploadToPinata(data_bytes, filename):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {
        "pinata_api_key": Config.PINATA_API_KEY,
        "pinata_secret_api_key": Config.PINATA_SECRET_KEY,
    }
    files = {"file": (filename, data_bytes)}
    response = requests.post(url, files=files, headers=headers, timeout=60)
    response_json = response.json()
    if "IpfsHash" not in response_json:
        raise Exception("Pinata upload failed: " + str(response_json))
    return response_json["IpfsHash"]

def downloadFromIpfs(ipfs_hash):
    ipfs_hash = str(ipfs_hash).strip()
    if isLegacyRecord(ipfs_hash):
        if os.path.exists(ipfs_hash):
            return open(ipfs_hash, "rb").read()
        raise Exception("Old local file not found - please re-upload record")

    gateways = [
        "https://gateway.pinata.cloud/ipfs/",
        "https://ipfs.io/ipfs/",
        "https://dweb.link/ipfs/",
    ]
    for gateway in gateways:
        try:
            response = requests.get(gateway + ipfs_hash, timeout=60)
            if response.status_code == 200 and len(response.content) > 0:
                return response.content
        except Exception:
            continue
    raise Exception("Could not download file from IPFS - check hash or wait and retry")

def decryptFromIpfs(ipfs_hash):
    ipfs_hash = str(ipfs_hash).strip()
    if isLegacyRecord(ipfs_hash):
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

def safeGetDecryptedFileBytes(ipfs_hash):
    try:
        return getDecryptedFileBytes(ipfs_hash)
    except Exception:
        return None
