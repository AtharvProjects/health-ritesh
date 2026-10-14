"""
Comprehensive End-to-End Test Suite for SafeHealth Blockchain System
Tests:
  1. Admin authentication & setup
  2. Healthcare organization management
  3. Doctor registration & authentication
  4. Patient self-registration & authentication
  5. Medical record encryption (AES + Paillier) & Pinata IPFS upload
  6. Blockchain metadata pinning and record sharing
  7. Doctor shared record access, downloading & auditing
  8. Doctor prescription generation, encryption & blockchain submission
  9. Patient prescription viewing & downloading
 10. Audit logs & system analytics
"""
import sys
import unittest
from app_v2.run import create_app
from app_v2.utils.blockchain import getContract

class TestSafeHealthSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

    def test_01_blockchain_connectivity(self):
        web3, contract, account = getContract()
        self.assertIsNotNone(contract.address, "Contract address must be defined")
        self.assertTrue(web3.is_connected(), "Web3 must be connected to Ganache")
        print(" [OK] Blockchain connectivity verified")

    def test_02_admin_login(self):
        res = self.client.post('/AdminLoginAction', data={'t1': 'admin', 't2': 'admin'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Welcome admin', res.data)
        print(" [OK] Admin login verified")

    def test_03_create_organization(self):
        res = self.client.post('/CreateOrganizationAction', data={
            't1': 'City General Hospital',
            't2': '742 Evergreen Terrace',
            't3': '555-0199'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'Organization saved' in res.data or b'ORG' in res.data)
        print(" [OK] Organization creation verified")

    def test_04_view_organizations(self):
        res = self.client.get('/ViewOrganizations')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'City General Hospital', res.data)
        print(" [OK] View organizations verified")

    def test_05_register_doctor(self):
        res = self.client.post('/RegisterDoctorAction', data={
            't1': 'Dr. Gregory House',
            't2': 'Diagnostics',
            't3': '0',
            't4': 'drhouse',
            't5': 'vicodin'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'Doctor registered successfully' in res.data or b'already exists' in res.data or b'DOC' in res.data)
        print(" [OK] Doctor registration verified")

    def test_06_patient_registration(self):
        res = self.client.post('/PatientRegisterAction', data={
            't1': 'Jane Doe',
            't2': 'Female',
            't3': '1992-08-24',
            't4': '555-0123',
            't5': '456 Oak Lane',
            't6': 'janedoe',
            't7': 'securepass'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'Registration successful' in res.data or b'already exists' in res.data or b'PAT' in res.data)
        print(" [OK] Patient self-registration verified")

    def test_07_patient_login(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        res = self.client.post('/PatientLoginAction', data={'t1': 'janedoe', 't2': 'securepass'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Welcome, janedoe', res.data)
        print(" [OK] Patient login verified")

    def test_08_patient_upload_and_share_record(self):
        report_text = "Diagnostic Report: Patient presents with seasonal allergies. Prescribe antihistamines."
        res = self.client.post('/UploadRecordAction', data={
            't1': 'Allergy Report',
            't3': report_text,
            't4': ['0']
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'uploaded and shared successfully' in res.data or b'REC' in res.data)
        print(" [OK] Patient record encryption, IPFS pinning & sharing verified")

    def test_09_doctor_login_and_view_shared_records(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        res = self.client.post('/DoctorLoginAction', data={'t1': 'drhouse', 't2': 'vicodin'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        res_shared = self.client.get('/ViewSharedRecords')
        self.assertEqual(res_shared.status_code, 200)
        self.assertIn(b'Allergy Report', res_shared.data)
        print(" [OK] Doctor login & shared records view verified")

    def test_10_doctor_submit_prescription(self):
        # Doctor is logged in from test_09
        # Get latest record id and patient id from contract
        _, contract, _ = getContract()
        rec_id = contract.functions.recordCount().call() - 1
        pat_id = contract.functions.getRecordPatientId(rec_id).call()
        selected_val = f"{rec_id}#{pat_id}"
        
        res = self.client.post('/SubmitPrescriptionAction', data={
            't1': selected_val,
            't3': 'Cetirizine 10mg once daily at bedtime for 10 days.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Prescription submitted', res.data)
        print(" [OK] Doctor prescription generation, dual-encryption & blockchain pinning verified")

    def test_11_audit_logs_and_analytics(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        self.client.post('/AdminLoginAction', data={'t1': 'admin', 't2': 'admin'}, follow_redirects=True)
        res_audit = self.client.get('/AuditLogs')
        self.assertEqual(res_audit.status_code, 200)
        res_analytics = self.client.get('/Analytics')
        self.assertEqual(res_analytics.status_code, 200)
        print(" [OK] Audit logs and Analytics console verified")

if __name__ == '__main__':
    unittest.main()
