import hre from "hardhat";

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Contract deploy ho rha ha address se:", deployer.address);

  // 1. Contract Factory
  const GoldSupplyChain =
    await hre.ethers.getContractFactory("GoldSupplyChain");

  // 2. Deploy
  console.log("Deploying...");
  const contract = await GoldSupplyChain.deploy();

  // Wait for it to finish
  await contract.waitForDeployment();
  const address = await contract.getAddress();

  console.log("✅ GoldSupplyChain live at:", address);

  // 3. Bogdan's 6 Addresses
  const list = [
    "0x86e9A17e91Fa708ebBE31910B24Fc50aA8BC6694",
    "0x6F69c758aa9B6cD5db3b93Eb1C71cBEC2D1cd709",
    "0xF59519beb56618840cF63e18c7A1641b76DBc9C8",
    "0x5562cCbe5ffCB2a94459552400209F0c9F57381B",
    "0xe03BDA30D27b33567DFeff7632027353A44e4a74",
    "0x0BFCB0A99418Dc528270086c445a1311E3fdD3D2",
    "0x2FC9A3fae5B69B89412f4C1C252DA92F0ef32E51",
    "0xF05936A42e55c7c3F060EF88f41CCde3f125593c",
  ];

  for (const addr of list) {
    console.log(`Whitelisting: ${addr}`);
    const tx = await contract.addToWhitelist(addr);
    await tx.wait();
    console.log("👍 Success!");
  }

  console.log("\n🚀 EVERYTHING IS READY!");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
