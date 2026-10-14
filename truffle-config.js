module.exports = {
  networks: {
    development: {
      host: "127.0.0.1",
      port: 8545,
      network_id: "*"
    }
  },

  contracts_directory: "./contracts",
  contracts_build_directory: "./build/contracts",
  migrations_directory: "./migrations",

  compilers: {
    solc: {
      version: "0.8.26",
      settings: {
        optimizer: {
          enabled: true,
          runs: 1
        },
        viaIR: true,
        evmVersion: "paris"
      }
    }
  }
};
