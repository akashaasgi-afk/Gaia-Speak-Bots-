import "@nomicfoundation/hardhat-toolbox";
import dotenv from "dotenv";
import "@tenderly/hardhat-tenderly";

// Load environment variables from .env file
dotenv.config();

/** @type import('hardhat/config').HardhatUserConfig */
const config = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      // viaIR: true,
    },
  },
  networks: {
    amoy: {
      url: process.env.AMOY_RPC_URL || "https://rpc-amoy.polygon.technology",
      accounts: process.env.PRIVATE_KEY ? [`0x${process.env.PRIVATE_KEY}`] : [],
      chainId: 80002,
    },
    hardhat: {
      chainId: 31337,
      // Allow deployment of large contracts on local network
      allowUnlimitedContractSize: true,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      allowUnlimitedContractSize: true,
    },
    tenderly:{
      url: "https://virtual.rpc.tenderly.co/Spancial/gaia-protocol/public/gaiaprotocol",
      chainId: 99980002
    }
  },
  tenderly: {
    project:process.env.TENDERLY_PROJECT ,
    username:process.env.TENDERLY_USERNAME 
  },
  etherscan: {
    apiKey: process.env.POLYGONSCAN_API_KEY || "YOUR_POLYGONSCAN_API_KEY",
  },
};

export default config;
