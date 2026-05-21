import "@nomicfoundation/hardhat-toolbox";

/** @type import('hardhat/config').HardhatUserConfig */
const config = {
  solidity: "0.8.20",
  networks: {
    amoy: {
      url: "https://rpc-amoy.polygon.technology",
      accounts: [], // Isay khali rehne dein
    },
  },
  etherscan: {
    apiKey: "YOUR_POLYGONSCAN_API_KEY", // Agar PolygonScan API key hai toh yahan dalien
  },
};

export default config;
