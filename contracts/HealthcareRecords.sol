// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Healthcare record system - stores metadata on chain, files stay on IPFS
contract HealthcareRecords {

    uint public adminCount;
    mapping(uint => Admin) public adminList;

    struct Admin {
        string username;
        string passwordHash;
    }

    uint public organizationCount;
    mapping(uint => Organization) public organizationList;

    struct Organization {
        string organizationName;
        string physicalAddress;
        string contactDetails;
        uint createdAt;
    }

    uint public doctorCount;
    mapping(uint => Doctor) public doctorList;

    struct Doctor {
        string name;
        string specialization;
        uint organizationId;
        string username;
        string passwordHash;
        uint registeredAt;
    }

    uint public patientCount;
    mapping(uint => Patient) public patientList;

    struct Patient {
        string name;
        string gender;
        string dateOfBirth;
        string contactNumber;
        string physicalAddress;
        string username;
        string passwordHash;
        uint registeredAt;
    }

    uint public recordCount;
    mapping(uint => MedicalRecord) public recordList;

    struct MedicalRecord {
        uint patientId;
        string ipfsHash;
        uint timestamp;
        string recordType;
        string fileName;
        bool prescriptionSubmitted;
        bool recordLocked;
    }

    uint public sharingCount;
    mapping(uint => RecordSharing) public sharingList;

    struct RecordSharing {
        uint recordId;
        uint patientId;
        uint organizationId;
        uint sharedTimestamp;
    }

    uint public prescriptionCount;
    mapping(uint => Prescription) public prescriptionList;

    struct Prescription {
        uint patientId;
        uint doctorId;
        uint recordId;
        string prescriptionHash;
        string fileName;
        uint timestamp;
        string status;
    }

    uint public accessCount;
    mapping(uint => AccessLog) public accessList;

    struct AccessLog {
        uint doctorId;
        uint recordId;
        uint patientId;
        uint organizationId;
        uint accessedAt;
    }

    mapping(string => uint) public adminUsernameToId;
    mapping(string => uint) public doctorUsernameToId;
    mapping(string => uint) public patientUsernameToId;
    mapping(uint => mapping(uint => bool)) public recordSharedWithOrg;
    mapping(uint => uint) public recordToPrescriptionId;

    event AdminCreated(uint indexed adminId);
    event OrganizationCreated(uint indexed organizationId);
    event DoctorRegistered(uint indexed doctorId);
    event PatientRegistered(uint indexed patientId);
    event MedicalRecordUploaded(uint indexed recordId);
    event RecordShared(uint indexed sharingId);
    event RecordShareRevoked(uint indexed recordId, uint indexed organizationId);
    event RecordAccessed(uint indexed accessId);
    event PrescriptionSubmitted(uint indexed prescriptionId);
    event PrescriptionViewed(uint indexed prescriptionId, uint viewerId);

    // setup admin account
    function saveAdmin(string memory username, string memory passwordHash) public {
        require(adminCount == 0, "Admin already exists");
        adminList[adminCount] = Admin(username, passwordHash);
        adminUsernameToId[username] = adminCount;
        emit AdminCreated(adminCount);
        adminCount++;
    }

    // admin creates organization
    function saveOrganization(
        string memory organizationName,
        string memory physicalAddress,
        string memory contactDetails
    ) public {
        organizationList[organizationCount] = Organization(
            organizationName,
            physicalAddress,
            contactDetails,
            block.timestamp
        );
        emit OrganizationCreated(organizationCount);
        organizationCount++;
    }

    // admin registers doctor
    function saveDoctor(
        string memory name,
        string memory specialization,
        uint organizationId,
        string memory username,
        string memory passwordHash
    ) public {
        require(organizationId < organizationCount, "Invalid organization");
        doctorList[doctorCount] = Doctor(
            name,
            specialization,
            organizationId,
            username,
            passwordHash,
            block.timestamp
        );
        doctorUsernameToId[username] = doctorCount;
        emit DoctorRegistered(doctorCount);
        doctorCount++;
    }

    // patient registration
    function savePatient(
        string memory name,
        string memory gender,
        string memory dateOfBirth,
        string memory contactNumber,
        string memory physicalAddress,
        string memory username,
        string memory passwordHash
    ) public {
        patientList[patientCount] = Patient(
            name,
            gender,
            dateOfBirth,
            contactNumber,
            physicalAddress,
            username,
            passwordHash,
            block.timestamp
        );
        patientUsernameToId[username] = patientCount;
        emit PatientRegistered(patientCount);
        patientCount++;
    }

    // save medical record after IPFS upload
    function saveMedicalRecord(
        uint patientId,
        string memory ipfsHash,
        string memory recordType,
        string memory fileName
    ) public {
        require(patientId < patientCount, "Invalid patient");
        recordList[recordCount] = MedicalRecord(
            patientId,
            ipfsHash,
            block.timestamp,
            recordType,
            fileName,
            false,
            false
        );
        emit MedicalRecordUploaded(recordCount);
        recordCount++;
    }

    // patient shares record with organization
    function shareRecord(uint recordId, uint patientId, uint organizationId) public {
        require(recordId < recordCount, "Invalid record");
        require(patientId < patientCount, "Invalid patient");
        require(organizationId < organizationCount, "Invalid organization");
        require(recordList[recordId].patientId == patientId, "Patient mismatch");
        require(!recordSharedWithOrg[recordId][organizationId], "Already shared");

        sharingList[sharingCount] = RecordSharing(
            recordId,
            patientId,
            organizationId,
            block.timestamp
        );
        recordSharedWithOrg[recordId][organizationId] = true;
        emit RecordShared(sharingCount);
        sharingCount++;
    }

    function revokeShare(uint recordId, uint patientId, uint organizationId) public {
        require(recordId < recordCount, "Invalid record");
        require(patientId < patientCount, "Invalid patient");
        require(organizationId < organizationCount, "Invalid organization");
        require(recordList[recordId].patientId == patientId, "Patient mismatch");
        require(recordSharedWithOrg[recordId][organizationId], "Not shared");

        recordSharedWithOrg[recordId][organizationId] = false;
        emit RecordShareRevoked(recordId, organizationId);
    }

    function isRecordSharedWithOrg(uint recordId, uint organizationId) public view returns (bool) {
        return recordSharedWithOrg[recordId][organizationId];
    }

    // check doctor access to shared record
    function isDoctorAuthorized(uint doctorId, uint recordId) public view returns (bool) {
        if (doctorId >= doctorCount || recordId >= recordCount) {
            return false;
        }
        uint orgId = doctorList[doctorId].organizationId;
        return recordSharedWithOrg[recordId][orgId];
    }

    // doctor opens shared record
    function accessSharedRecord(uint doctorId, uint recordId) public returns (string memory) {
        require(isDoctorAuthorized(doctorId, recordId), "Not authorized");

        uint patientId = recordList[recordId].patientId;
        uint organizationId = doctorList[doctorId].organizationId;

        accessList[accessCount] = AccessLog(
            doctorId,
            recordId,
            patientId,
            organizationId,
            block.timestamp
        );
        emit RecordAccessed(accessCount);
        accessCount++;

        return recordList[recordId].ipfsHash;
    }

    // doctor submits prescription - one per record only
    function savePrescription(
        uint doctorId,
        uint patientId,
        uint recordId,
        string memory prescriptionHash,
        string memory fileName
    ) public {
        require(doctorId < doctorCount, "Invalid doctor");
        require(patientId < patientCount, "Invalid patient");
        require(recordId < recordCount, "Invalid record");
        require(recordList[recordId].patientId == patientId, "Patient mismatch");
        require(!recordList[recordId].prescriptionSubmitted, "Already submitted");
        require(!recordList[recordId].recordLocked, "Record locked");
        require(isDoctorAuthorized(doctorId, recordId), "Not authorized");

        prescriptionList[prescriptionCount] = Prescription(
            patientId,
            doctorId,
            recordId,
            prescriptionHash,
            fileName,
            block.timestamp,
            "SUBMITTED"
        );

        recordList[recordId].prescriptionSubmitted = true;
        recordList[recordId].recordLocked = true;
        recordToPrescriptionId[recordId] = prescriptionCount;

        emit PrescriptionSubmitted(prescriptionCount);
        prescriptionCount++;
    }

    function logPrescriptionViewed(uint prescriptionId, uint viewerId) public {
        require(prescriptionId < prescriptionCount, "Invalid prescription");
        emit PrescriptionViewed(prescriptionId, viewerId);
    }

    // login helpers - Flask compares returned hash with user input
    function getAdminUsername(uint i) public view returns (string memory) {
        return adminList[i].username;
    }

    function getAdminPasswordHash(uint i) public view returns (string memory) {
        return adminList[i].passwordHash;
    }

    function getDoctorUsername(uint i) public view returns (string memory) {
        return doctorList[i].username;
    }

    function getDoctorPasswordHash(uint i) public view returns (string memory) {
        return doctorList[i].passwordHash;
    }

    function getDoctorOrganizationId(uint i) public view returns (uint) {
        return doctorList[i].organizationId;
    }

    function getPatientUsername(uint i) public view returns (string memory) {
        return patientList[i].username;
    }

    function getPatientPasswordHash(uint i) public view returns (string memory) {
        return patientList[i].passwordHash;
    }

    function getRecordIpfsHash(uint i) public view returns (string memory) {
        return recordList[i].ipfsHash;
    }

    function getRecordPatientId(uint i) public view returns (uint) {
        return recordList[i].patientId;
    }

    function getRecordType(uint i) public view returns (string memory) {
        return recordList[i].recordType;
    }

    function getRecordFileName(uint i) public view returns (string memory) {
        return recordList[i].fileName;
    }

    function getRecordTimestamp(uint i) public view returns (uint) {
        return recordList[i].timestamp;
    }

    function isRecordLocked(uint i) public view returns (bool) {
        return recordList[i].recordLocked;
    }

    function getPrescriptionHash(uint i) public view returns (string memory) {
        return prescriptionList[i].prescriptionHash;
    }

    function getPrescriptionFileName(uint i) public view returns (string memory) {
        return prescriptionList[i].fileName;
    }

    function getPrescriptionStatus(uint i) public view returns (string memory) {
        return prescriptionList[i].status;
    }

    function getPrescriptionByRecord(uint recordId) public view returns (uint) {
        return recordToPrescriptionId[recordId];
    }

    function getOrganizationName(uint i) public view returns (string memory) {
        return organizationList[i].organizationName;
    }

    function getOrganizationAddress(uint i) public view returns (string memory) {
        return organizationList[i].physicalAddress;
    }

    function getOrganizationContact(uint i) public view returns (string memory) {
        return organizationList[i].contactDetails;
    }

    function getDoctorName(uint i) public view returns (string memory) {
        return doctorList[i].name;
    }

    function getDoctorSpecialization(uint i) public view returns (string memory) {
        return doctorList[i].specialization;
    }

    function getPatientName(uint i) public view returns (string memory) {
        return patientList[i].name;
    }

    function getPatientGender(uint i) public view returns (string memory) {
        return patientList[i].gender;
    }

    function getPatientDob(uint i) public view returns (string memory) {
        return patientList[i].dateOfBirth;
    }

    function getPatientContact(uint i) public view returns (string memory) {
        return patientList[i].contactNumber;
    }

    function getPatientAddress(uint i) public view returns (string memory) {
        return patientList[i].physicalAddress;
    }

    function getSharingRecordId(uint i) public view returns (uint) {
        return sharingList[i].recordId;
    }

    function getSharingPatientId(uint i) public view returns (uint) {
        return sharingList[i].patientId;
    }

    function getSharingOrganizationId(uint i) public view returns (uint) {
        return sharingList[i].organizationId;
    }

    function getSharingTimestamp(uint i) public view returns (uint) {
        return sharingList[i].sharedTimestamp;
    }

    function getAccessDoctorId(uint i) public view returns (uint) {
        return accessList[i].doctorId;
    }

    function getAccessRecordId(uint i) public view returns (uint) {
        return accessList[i].recordId;
    }

    function getAccessPatientId(uint i) public view returns (uint) {
        return accessList[i].patientId;
    }

    function getAccessOrganizationId(uint i) public view returns (uint) {
        return accessList[i].organizationId;
    }

    function getAccessTimestamp(uint i) public view returns (uint) {
        return accessList[i].accessedAt;
    }
}
