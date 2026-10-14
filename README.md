# SafeHealth: Blockchain-Based Healthcare Record Management System

SafeHealth is a decentralized, cryptographically secure healthcare records management system. It combines an Ethereum smart contract on the blockchain with IPFS decentralized storage and dual-layer encryption (AES-256 + Paillier Homomorphic Cryptography) to ensure patient confidentiality, auditability, and tamper-proof health record sharing.

---

## 🌟 Key Features

1. **Role-Based Access Control**:
   - **Admin Portal**: System administrator initializes healthcare organizations (hospitals/clinics), approves doctors, and audits access logs.
   - **Doctor Portal**: View patient records shared with the doctor's hospital, access medical histories, and issue cryptographically signed prescriptions.
   - **Patient Portal**: Self-register, upload medical reports, encrypt files, selectively share records with specific healthcare organizations, and revoke access at any time.

2. **Dual-Layer Hybrid Cryptography**:
   - **AES-256 (CBC)**: Symmetric encryption for rapid payload securing.
   - **Paillier Homomorphic Cryptosystem (2048-bit)**: Asymmetric layer enabling mathematical confidentiality on encrypted data chunks.
   - **Decentralized Storage (Pinata IPFS)**: Encrypted ciphertext payloads are securely pinned to IPFS, ensuring records are resilient and tamper-proof.
   - **Blockchain Metadata**: Smart contract (`HealthcareRecords.sol`) enforces permissions, ownership, and immutability for access logs and record hashes.

3. **Complete Auditability & Analytics**:
   - Real-time cryptographic access logging for every view or download.
   - Interactive Analytics Dashboard with Chart.js visualizations for transactions, organizations, and cryptographic latency metrics.

---

## 🚀 Quick Start (1-Click on Windows)

Simply double-click:
```bat
start_all.bat
```
This script will:
1. Detect or start your local Ganache blockchain node on `127.0.0.1:8545`.
2. Verify smart contract compilation and migration.
3. Launch the web application on `http://127.0.0.1:5000/` and open your default browser.

---

## 🛠 Manual Step-by-Step Setup

### 1. Start Ganache Blockchain
```bash
# In terminal 1:
run_ganache.bat
# Or manually:
npx ganache --host 127.0.0.1 --port 8545 --mnemonic "candy maple cake sugar pudding cream honey rich smooth crumble sweet treat"
```

### 2. Compile and Deploy Smart Contracts
```bash
# In terminal 2:
deploy_contracts.bat
# Or manually:
npx truffle migrate --reset
```

### 3. Start the Web Application
```bash
# In terminal 3:
start_app.bat
# Or manually:
python app_v2/run.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🧪 Running the Automated Test Suite

An automated end-to-end test suite (`test_all.py`) is included to verify all components (Blockchain, Smart Contracts, IPFS Pinning, Dual Cryptography, Roles, and File Downloads):

```bash
python test_all.py
```

Expected output:
```
Ran 11 tests in 51s
OK
 [OK] Blockchain connectivity verified
 [OK] Admin login verified
 [OK] Organization creation verified
 [OK] View organizations verified
 [OK] Doctor registration verified
 [OK] Patient self-registration verified
 [OK] Patient login verified
 [OK] Patient record encryption, IPFS pinning & sharing verified
 [OK] Doctor login & shared records view verified
 [OK] Doctor prescription generation, dual-encryption & blockchain pinning verified
 [OK] Audit logs and Analytics console verified
```

---

## 🔑 Default Credentials

- **Admin Login**:
  - URL: `/AdminLogin`
  - Username: `admin`
  - Password: `admin` (Initialized on blockchain upon first login)

- **Doctor Login**:
  - URL: `/DoctorLogin`
  - Created by Admin via `/RegisterDoctor`

- **Patient Login**:
  - URL: `/PatientLogin`
  - Self-registered via `/PatientRegister`
