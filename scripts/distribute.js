import hre from "hardhat";

async function main() {
  // Ye wahi address hai jo aapka pichli baar terminal par aaya tha
  const contractAddress = "0x5FbDB2315678afecb367f032d93F642f64180aa3";
  const contract = await hre.ethers.getContractAt(
    "GoldSupplyChain",
    contractAddress,
  );

  const wallets = [
    "0x86e9A17e91Fa708ebBE31910B24Fc50aA8BC6694",
    "0x6F69c758aa9B6cD5db3b93Eb1C71cBEC2D1cd709",
    "0xF59519beb56618840cF63e18c7A1641b76DBc9C8",
    "0x5562cCbe5ffCB2a94459552400209F0c9F57381B",
    "0xe03BDA30D27b33567DFeff7632027353A44e4a74",
    "0x0BFCB0A99418Dc528270086c445a1311E3fdD3D2",
    "0x2FC9A3fae5B69B89412f4C1C252DA92F0ef32E51",
    "0xF05936A42e55c7c3F060EF88f41CCde3f125593c",
  ];

  console.log("🚀 Starting Token Distribution...");

  for (const wallet of wallets) {
    try {
      console.log(`Sending 100 GOLD to ${wallet}...`);
      const tx = await contract.mint(wallet, 100);
      await tx.wait();
      console.log("✅ Success!");
    } catch (err) {
      console.log(`❌ Error with ${wallet}:`, err.message);
    }
  }

  console.log("\n🎯 Mission Accomplished: All wallets updated!");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
