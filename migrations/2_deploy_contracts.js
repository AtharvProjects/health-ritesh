const HealthcareRecords = artifacts.require("HealthcareRecords");

module.exports = function (deployer) {
  deployer.deploy(HealthcareRecords);
};
