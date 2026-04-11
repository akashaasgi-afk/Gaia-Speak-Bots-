import pkg from "hardhat";
const { ethers } = pkg;

async function main() {
  // ═══════════════════════════════════════════════════════════════════════
  // DEPLOYMENT CONFIGURATION (from instruction.txt)
  // For local testing: use Hardhat test accounts
  // For mainnet: use real addresses from instruction.txt
  // ═══════════════════════════════════════════════════════════════════════

  // Get signers
  const signers = await ethers.getSigners();
  if (!signers || signers.length === 0) {
    throw new Error("❌ ERROR: No accounts found! Check hardhat.config.js private keys.");
  }

  const deployer = signers[0];
  const network = (await ethers.provider.getNetwork()).name;

  // Use test accounts for local/hardhat networks, real addresses for live networks
  let FOUNDER, PIONEER_1, PIONEER_2, PIONEER_3, PIONEER_4, PIONEER_5, OPERATIONS, GOLD_RESERVE;
  let CHAINLINK_ETH_FEED, CHAINLINK_SILVER_FEED;

  if (network === 'hardhat' || network === 'localhost') {
    // Local testing - use Hardhat test accounts
    console.log("🔬 LOCAL TESTING MODE - Using Hardhat test accounts");
    FOUNDER = signers[0].address;          // Deployer
    PIONEER_1 = signers[1].address;
    PIONEER_2 = signers[2].address;
    PIONEER_3 = signers[3].address;
    PIONEER_4 = signers[4].address;
    PIONEER_5 = signers[5].address;
    OPERATIONS = signers[6].address;
    GOLD_RESERVE = signers[7].address;
    // Use mock addresses for Chainlink feeds (not used on local network)
    CHAINLINK_ETH_FEED = signers[8].address;
    CHAINLINK_SILVER_FEED = signers[9].address;
  } else {
    // Live network - use real addresses from instruction.txt
    console.log("🌐 LIVE NETWORK MODE - Using configured addresses");
    FOUNDER = '0x86e9A17e91Fa708ebBE31910B24Fc50aA8BC6694';
    PIONEER_1 = '0x6F69c758aa9B6cD5db3b93Eb1C71cBEC2D1cd709';
    PIONEER_2 = '0xF59519beb56618840cF63e18c7A1641b76DBc9C8';
    PIONEER_3 = '0x5562cCbe5ffCB2a94459552400209F0c9F57381B';
    PIONEER_4 = '0xe03BDA30D27b33567DFeff7632027353A44e4a74';
    PIONEER_5 = '0x0BFCB0A99418Dc528270086c445a1311E3fdD3D2';
    OPERATIONS = '0x2FC9A3fAe5B69B89412f4C1C252DA92F0ef32E51';
    GOLD_RESERVE = '0xF05936A42e55c7c3F060EF88f41CCde3f125593c';
    CHAINLINK_ETH_FEED = '0x001382149eBa3441043c1c66972b4772963f5D43'; // ETH/USD on Amoy
    CHAINLINK_SILVER_FEED = '0x379589227b15F1a12195D3f2d90bBc9F31f95235'; // XAG/USD
  }
  console.log("\n" + "═".repeat(70));
  console.log("🚀 GAIASPEAK PROTOCOL DEPLOYMENT START");
  console.log("═".repeat(70));
  console.log("Deployer Address:", deployer.address);
  console.log("Network:", (await ethers.provider.getNetwork()).name);
  console.log("═".repeat(70) + "\n");

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 1: Deploy GaiaSpeakProtocol (initialOwner = FOUNDER)
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 1️⃣  Deploying GaiaSpeakProtocol...");
  const GaiaSpeakProtocol = await ethers.getContractFactory("GaiaSpeakProtocol");
  const protocol = await GaiaSpeakProtocol.deploy();
  await protocol.waitForDeployment();
  const protocolAddress = await protocol.getAddress();
  console.log("✅ GaiaSpeakProtocol deployed at:", protocolAddress);
  console.log("   (implementation address — will be initialized next)\n");

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 2: Deploy GaiaSpeakToken (GSG) with Protocol address
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 2️⃣  Deploying GaiaSpeakToken (GSG)...");
  const GaiaSpeakToken = await ethers.getContractFactory("GaiaSpeakToken");
  const goldToken = await GaiaSpeakToken.deploy();
  await goldToken.waitForDeployment();
  const goldTokenAddress = await goldToken.getAddress();
  console.log("✅ GaiaSpeakToken deployed at:", goldTokenAddress + "\n");

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 3: Deploy GaiaSpeakSilverToken (GSS) with Protocol address
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 3️⃣  Deploying GaiaSpeakSilverToken (GSS)...");
  const GaiaSpeakSilverToken = await ethers.getContractFactory("GaiaSpeakSilverToken");
  const silverToken = await GaiaSpeakSilverToken.deploy();
  await silverToken.waitForDeployment();
  const silverTokenAddress = await silverToken.getAddress();
  console.log("✅ GaiaSpeakSilverToken deployed at:", silverTokenAddress + "\n");


  // ═══════════════════════════════════════════════════════════════════════
  // STEP 4: Deploy GaiaSpeakNFT with Protocol + GSG + GSS addresses
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 4️⃣  Deploying GaiaSpeakNFT...");
  const GaiaSpeakNFT = await ethers.getContractFactory("GaiaSpeakNFT");
  const nft = await GaiaSpeakNFT.deploy();
  await nft.waitForDeployment();
  const nftAddress = await nft.getAddress();
  console.log("✅ GaiaSpeakNFT deployed at:", nftAddress + "\n");

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 5: Initialize GaiaSpeakProtocol with all wallet addresses
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 5️⃣  Initializing GaiaSpeakProtocol...");
  const initTx = await protocol.initialize(
    FOUNDER,                                    // _founder
    GOLD_RESERVE,                               // _goldReserve
    GOLD_RESERVE,                               // _silverReserve (same as gold for now)
    OPERATIONS,                                 // _operations
    OPERATIONS,                                 // _referral
    [PIONEER_1, PIONEER_2, PIONEER_3, PIONEER_4, PIONEER_5],  // _pioneers (5)
    [FOUNDER, GOLD_RESERVE, OPERATIONS],        // _guardians (3)
    CHAINLINK_ETH_FEED,                         // _ethUsdFeed (Amoy)
    CHAINLINK_SILVER_FEED,                      // _silverUsdFeed (mock on testnet)
    [FOUNDER, GOLD_RESERVE, OPERATIONS, PIONEER_1, PIONEER_2] // _oracleAddresses (5 - use temp addresses)
  );
  await initTx.wait();
  console.log("✅ GaiaSpeakProtocol initialized\n");

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 6: Call setGoldTokenContract() on Protocol with GSG address
  // NOTE: These functions require onlyOwner, so we need to call them from
  // the founder's wallet (or use impersonation in testing)
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 6️⃣  Setting Gold Token Contract on Protocol...");

  // For local/testnet testing, if deployer is not owner, try to impersonate
  // If this is mainnet, the deployer should be the founder OR the founder should execute this
  try {
    const setGoldTx = await protocol.setGoldTokenContract(goldTokenAddress);
    await setGoldTx.wait();
    console.log("✅ Gold token contract set\n");
  } catch (error) {
    if (error.message.includes("Ownable: caller is not the owner")) {
      console.log("⚠️  Deployer is not owner. Attempting to call from founder wallet...");
      // Get a signer for the founder wallet (only works on local/test networks)
      const founderSigner = await ethers.provider.getSigner(FOUNDER);
      const protocolAsFounder = protocol.connect(founderSigner);
      const setGoldTx = await protocolAsFounder.setGoldTokenContract(goldTokenAddress);
      await setGoldTx.wait();
      console.log("✅ Gold token contract set (via founder)\n");
    } else {
      throw error;
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 7: Call setSilverTokenContract() on Protocol with GSS address
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 7️⃣  Setting Silver Token Contract on Protocol...");
  try {
    const setSilverTx = await protocol.setSilverTokenContract(silverTokenAddress);
    await setSilverTx.wait();
    console.log("✅ Silver token contract set\n");
  } catch (error) {
    if (error.message.includes("Ownable: caller is not the owner")) {
      console.log("⚠️  Deployer is not owner. Attempting to call from founder wallet...");
      const founderSigner = await ethers.provider.getSigner(FOUNDER);
      const protocolAsFounder = protocol.connect(founderSigner);
      const setSilverTx = await protocolAsFounder.setSilverTokenContract(silverTokenAddress);
      await setSilverTx.wait();
      console.log("✅ Silver token contract set (via founder)\n");
    } else {
      throw error;
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 8: Call setNFTContract() on Protocol with NFT address
  // ═══════════════════════════════════════════════════════════════════════
  console.log("STEP 8️⃣  Setting NFT Contract on Protocol...");
  try {
    const setNFTTx = await protocol.setNFTContract(nftAddress);
    await setNFTTx.wait();
    console.log("✅ NFT contract set\n");
  } catch (error) {
    if (error.message.includes("Ownable: caller is not the owner")) {
      console.log("⚠️  Deployer is not owner. Attempting to call from founder wallet...");
      const founderSigner = await ethers.provider.getSigner(FOUNDER);
      const protocolAsFounder = protocol.connect(founderSigner);
      const setNFTTx = await protocolAsFounder.setNFTContract(nftAddress);
      await setNFTTx.wait();
      console.log("✅ NFT contract set (via founder)\n");
    } else {
      throw error;
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Initialize Token Contracts
  // ═══════════════════════════════════════════════════════════════════════
  console.log("Initializing Token Contracts...");

  // Initialize Gold Token
  const goldInitTx = await goldToken.initialize(
    protocolAddress,
    ethers.parseEther("0.01"),  // 0.01 MATIC monthly membership (~$0.003)
    "GaiaSpeakToken",
    "GSG"
  );
  await goldInitTx.wait();
  console.log("✅ GaiaSpeakToken initialized\n");

  // Initialize Silver Token
  // NOTE: GaiaSpeakSilverToken takes 2 params (not 4 like GaiaspeakToken)
  const silverInitTx = await silverToken.initialize(
    protocolAddress,
    ethers.parseEther("0.01")  // 0.01 MATIC monthly membership
  );
  await silverInitTx.wait();
  console.log("✅ GaiaSpeakSilverToken initialized\n");

  // ═══════════════════════════════════════════════════════════════════════
  // FINAL SUMMARY
  // ═══════════════════════════════════════════════════════════════════════
  console.log("═".repeat(70));
  console.log("✅ DEPLOYMENT COMPLETE!");
  console.log("═".repeat(70));
  console.log("\n📋 DEPLOYMENT SUMMARY:");
  console.log("─".repeat(70));
  console.log("Protocol Address:      ", protocolAddress);
  console.log("Gold Token (GSG):      ", goldTokenAddress);
  console.log("Silver Token (GSS):    ", silverTokenAddress);
  console.log("NFT Contract:          ", nftAddress);
  console.log("─".repeat(70));
  console.log("\n💰 WALLET CONFIGURATION:");
  console.log("─".repeat(70));
  console.log("Founder:               ", FOUNDER);
  console.log("Gold Reserve:          ", GOLD_RESERVE);
  console.log("Operations:            ", OPERATIONS);
  console.log("Pioneers:              ");
  console.log("  1:", PIONEER_1);
  console.log("  2:", PIONEER_2);
  console.log("  3:", PIONEER_3);
  console.log("  4:", PIONEER_4);
  console.log("  5:", PIONEER_5);
  console.log("─".repeat(70) + "\n");

  console.log("═".repeat(70) + "\n");
}

main().catch((error) => {
  console.error("\n❌ FATAL ERROR:");
  console.error(error);
  process.exitCode = 1;
});
