import os
import time
import json
import base64
import pickle
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from phe import paillier
from phe.paillier import EncryptedNumber

from app_v2.config import Config, AppState

def loadOrCreateKeys():
    aes_file = os.path.join(Config.KEYS_FOLDER, "aes_key.bin")
    paillier_file = os.path.join(Config.KEYS_FOLDER, "paillier_keys.pkl")

    if os.path.exists(aes_file):
        AppState.aes_key = open(aes_file, "rb").read()
    else:
        AppState.aes_key = get_random_bytes(32)
        open(aes_file, "wb").write(AppState.aes_key)

    if os.path.exists(paillier_file):
        key_data = pickle.load(open(paillier_file, "rb"))
        AppState.paillier_public_key = key_data["public"]
        AppState.paillier_private_key = key_data["private"]
    else:
        AppState.paillier_public_key, AppState.paillier_private_key = paillier.generate_paillier_keypair(n_length=2048)
        pickle.dump(
            {"public": AppState.paillier_public_key, "private": AppState.paillier_private_key},
            open(paillier_file, "wb"),
        )

def aesEncrypt(data_bytes):
    cipher = AES.new(AppState.aes_key, AES.MODE_CBC)
    encrypted = cipher.encrypt(pad(data_bytes, AES.block_size))
    return cipher.iv + encrypted

def aesDecrypt(data_bytes):
    iv = data_bytes[:16]
    encrypted = data_bytes[16:]
    cipher = AES.new(AppState.aes_key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(encrypted), AES.block_size)

def paillierEncrypt(data_bytes):
    chunk_size = 100
    chunks = []
    for i in range(0, len(data_bytes), chunk_size):
        chunk = data_bytes[i : i + chunk_size]
        number = int.from_bytes(chunk, "big")
        encrypted_number = AppState.paillier_public_key.encrypt(number)
        chunks.append(str(encrypted_number.ciphertext()))
    return json.dumps({"chunks": chunks, "total_length": len(data_bytes)})

def paillierDecrypt(data_json):
    data = json.loads(data_json)
    result = b""
    for chunk in data["chunks"]:
        encrypted_number = EncryptedNumber(AppState.paillier_public_key, int(chunk))
        number = AppState.paillier_private_key.decrypt(encrypted_number)
        chunk_bytes = number.to_bytes((number.bit_length() + 7) // 8, "big")
        result += chunk_bytes
    return result[: data["total_length"]]

def doubleEncrypt(data_bytes):
    start = time.time()
    aes_data = aesEncrypt(data_bytes)
    final_data = paillierEncrypt(aes_data)
    encrypted_text = base64.b64encode(final_data.encode("utf-8")).decode("ascii")
    AppState.encryption_times.append(round((time.time() - start) * 1000, 2))
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
        AppState.decryption_times.append(round((time.time() - start) * 1000, 2))
    return plain_data
