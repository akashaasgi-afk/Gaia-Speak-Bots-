import pkg from "hardhat";
const { ethers } = pkg;

async function main() {
  // 1. Signers hasil karna (Security Check ke sath)
  const signers = await ethers.getSigners();

  if (!signers || signers.length === 0) {
    throw new Error(
      "❌ ERROR: Koi account nahi mila! hardhat.config.js mein apni Private Key check karein.",
    );
  }

  const deployer = signers[0];
  console.log("--------------------------------------------------");
  console.log("🚀 Deployment Start ho rahi hai...");
  console.log("Wallet Address:", deployer.address);
  console.log("--------------------------------------------------");

  // Bogdan ka Main Founder Address (Jo Owner banega)
  const founderAddress = "0x86e9A17e91Fa708ebBE31910B24Fc50aaA8BC6694";

  // 2. Contract Factory hasil karna
  const GoldSupplyChain = await ethers.getContractFactory("GoldSupplyChain");

  // 3. Deploy (Bogdan ka address constructor mein bhej rahe hain)
  console.log("📦 Deploying GoldSupplyChain...");
  const contract = await GoldSupplyChain.deploy(founderAddress);

  // Deployment confirm hone ka intezar
  await contract.waitForDeployment();
  const contractAddress = await contract.getAddress();

  console.log("\n✅ SUCCESS: GoldSupplyChain live at:", contractAddress);
  console.log("👑 Owner set to:", founderAddress);
  console.log("--------------------------------------------------\n");

  // 4. Bogdan's Whitelist Addresses (Wahi purani list jo aapne di thi)
  const list = [
    "0x86e9A17e91Fa708ebBE31910B24Fc50aaA8BC6694",
    "0x6F69c758aa9B6cD5db3b93Eb1C71cBEC2D1cd709",
    "0xF59519beb56618840cF63e18c7A1641b76DBc9C8",
    "0x5562cCbe5ffCB2a94459552400209F0c9F57381B",
    "0xe03BDA30D27b33567DFeff7632027353A44e4a74",
    "0x0BFCB0A99418Dc528270086c445a1311E3fdD3D2",
    "0x2FC9A3fae5B69B89412f4C1C252DA92F0ef32E51",
    "0xF05936A42e55c7c3F060EF88f41CCde3f125593c",
  ];

  console.log("📝 Whitelisting process start ho raha hai...");

  // Loop jo har address ko whitelist karega
  for (const addr of list) {
    try {
      console.log(`Adding to Whitelist: ${addr}`);
      const tx = await contract.addToWhitelist(addr);
      await tx.wait(); // Transaction confirm hone ka intezar
      console.log("👍 Success!");
    } catch (err) {
      console.log(
        `⚠️ Skip: ${addr} shayad pehle se whitelist hai ya error aaya.`,
      );
    }
  }

  console.log("\n🚀 EVERYTHING IS READY!");
  console.log("==================================================");
  console.log("FINAL CONTRACT ADDRESS:", contractAddress);
  console.log("==================================================");
}

main().catch((error) => {
  console.error("\n❌ FATAL ERROR:");
  console.error(error);
  process.exitCode = 1;
});
