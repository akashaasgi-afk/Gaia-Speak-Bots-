// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol";
import "./libraries/OracleLib.sol";
import "./libraries/StageLib.sol";
import "./libraries/DeadManLib.sol";
import "./libraries/GuardianLib.sol";

// ═══════════════════════════════════════════════════════════════════════════
// GAIASPEAK PROTOCOL v2
// Master contract — single source of truth
// Changes from v1:
//   P-1: Removed goldGramsPurchased/Redeemed — no reserve model
//   P-2: Removed RED_STAGE_ENTRY/EXIT ratio constants
//   P-3: Removed recordGoldPurchase/Redemption functions
//   P-4: Replaced getBackingRatio with getOracleHealth
//   P-5: Replaced checkRedStage ratio logic with oracle health check
//   P-6: Added confirmFirstPublicPurchase — auto YELLOW trigger
//   P-7: Added pioneerRewardActive mapping + deactivatePioneerReward
// ═══════════════════════════════════════════════════════════════════════════

contract GaiaSpeakProtocol is
    UUPSUpgradeable,
    OwnableUpgradeable,
    PausableUpgradeable
{
    // ─── STAGE SYSTEM ────────────────────────────────────────────────────
    enum Stage { GREEN, YELLOW, GOLD, BLUE, RED, WHITE }

    Stage public currentStage;
    Stage private _stageBeforeRed; // Preserved so RED exits correctly

    // ─── WALLETS ─────────────────────────────────────────────────────────
    address public founderWallet;
    address public goldReserveWallet;
    address public silverReserveWallet;
    address public operationsWallet;
    address public referralWallet;
    address[5] public majorPioneerWallets;

    // ─── TOKEN CONTRACTS ─────────────────────────────────────────────────
    address public goldTokenContract;
    address public silverTokenContract;
    address public nftContract;

    // ─── ORACLE SYSTEM ───────────────────────────────────────────────────
    // Chainlink feeds
    AggregatorV3Interface public ethUsdFeed;
    AggregatorV3Interface public silverUsdFeed;

    // 5-oracle gold price consensus network
    address[5] public oracleAddresses;

    // ─── ORACLE HEALTH (replaces reserve tracking — P-1, P-2) ────────────
    uint256 public lastOracleHealthCheck;
    bool    public oracleHealthy;

    // ─── PIONEER REWARD SYSTEM (P-7) ─────────────────────────────────────
    mapping(address => bool) public pioneerRewardActive;

    // ─── AUTO-YELLOW TRIGGER (P-6) ───────────────────────────────────────
    bool public firstPublicPurchaseComplete;

    // ─── GUARDIAN SYSTEM ─────────────────────────────────────────────────
    address[3] public guardians;
    mapping(address => bool) public isGuardian;
    mapping(address => bool) public guardianPauseApproval;
    uint8 public pauseApprovalCount;

    // ─── DEAD-MAN SWITCH ─────────────────────────────────────────────────
    uint256 public lastHeartbeat;
    uint256 public constant HEARTBEAT_INTERVAL = 30 days;
    bool    public deadManActive;
    bool    public systemLocked;

    // Death proof verification
    mapping(bytes32 => bool) public deathProofSubmitted;
    bytes32 public familyProofId;
    bytes32 public companyProofId;
    bytes32 public thirdPartyProofId;

    // Pioneer resurrection
    mapping(address => bool) public hasApprovedResurrection;
    uint8 public resurrectionApprovalCount;

    // ─── LEGACY MODE ─────────────────────────────────────────────────────
    bool    public legacyModeActive;
    address public legacyWallet;

    // ─── TIMELOCK ────────────────────────────────────────────────────────
    uint256 public constant TIMELOCK_DELAY = 48 hours;
    mapping(bytes32 => uint256) public timelockScheduled;

    // ─── FLASH LOAN PROTECTION ───────────────────────────────────────────
    mapping(address => uint256) public lastPurchaseBlock;

    // ═══════════════════════════════════════════════════════════════════════
    // EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    event StageChanged(Stage indexed newStage, Stage indexed previousStage);
    event OracleFailureDetected(uint256 timestamp, uint256 responsiveOracles);
    event OracleRecovered(uint256 timestamp);
    event FirstPublicPurchaseConfirmed(uint256 timestamp);
    event PioneerRewardDeactivated(address indexed pioneer, uint256 timestamp);
    event PioneerRewardActivated(address indexed pioneer);
    event GuardianPauseApproved(address indexed guardian);
    event DeadManTriggered(uint256 timestamp);
    event DeathProofSubmitted(address indexed guardian, uint256 timestamp);
    event ResurrectionApproved(address indexed pioneer);
    event Resurrected(address indexed by, uint256 timestamp);
    event LegacyModeActivated(address indexed legacyWallet);
    event HeartbeatReceived(uint256 timestamp);
    event TimelockScheduled(bytes32 indexed actionId, uint256 executeAfter);
    event TimelockExecuted(bytes32 indexed actionId);
    event WalletUpdated(string walletType, address newAddress);
    event OracleAddressUpdated(uint8 index, address newOracle);

    // ═══════════════════════════════════════════════════════════════════════
    // MODIFIERS
    // ═══════════════════════════════════════════════════════════════════════

    modifier onlyToken() {
        require(
            msg.sender == goldTokenContract ||
            msg.sender == silverTokenContract,
            "Only token contracts"
        );
        _;
    }

    modifier onlyGuardian() {
        require(isGuardian[msg.sender], "Only guardians");
        _;
    }

    modifier onlyFounderOrLegacy() {
        require(
            msg.sender == founderWallet ||
            (legacyModeActive && msg.sender == legacyWallet),
            "Only founder or legacy"
        );
        _;
    }

    modifier notLocked() {
        require(!systemLocked, "System is locked");
        _;
    }

    modifier timelocked(bytes32 actionId) {
        if (timelockScheduled[actionId] == 0) {
            timelockScheduled[actionId] = block.timestamp + TIMELOCK_DELAY;
            emit TimelockScheduled(actionId, timelockScheduled[actionId]);
            return;
        }
        require(
            block.timestamp >= timelockScheduled[actionId],
            "Timelock not expired"
        );
        delete timelockScheduled[actionId];
        emit TimelockExecuted(actionId);
        _;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZER
    // ═══════════════════════════════════════════════════════════════════════

    function initialize(
        address _founder,
        address _goldReserve,
        address _silverReserve,
        address _operations,
        address _referral,
        address[5] memory _pioneers,
        address[3] memory _guardians,
        address _ethUsdFeed,
        address _silverUsdFeed,
        address[5] memory _oracleAddresses
    ) external initializer {
        __Ownable_init();
        __Pausable_init();
        __UUPSUpgradeable_init();
        _transferOwnership(_founder);

        // Wallets
        founderWallet       = _founder;
        goldReserveWallet   = _goldReserve;
        silverReserveWallet = _silverReserve;
        operationsWallet    = _operations;
        referralWallet      = _referral;
        majorPioneerWallets = _pioneers;

        // Guardians
        for (uint i = 0; i < 3; i++) {
            guardians[i]           = _guardians[i];
            isGuardian[_guardians[i]] = true;
        }

        // Oracles
        ethUsdFeed    = AggregatorV3Interface(_ethUsdFeed);
        silverUsdFeed = AggregatorV3Interface(_silverUsdFeed);
        oracleAddresses = _oracleAddresses;

        // Pioneer rewards active at launch (P-7)
        for (uint i = 0; i < 5; i++) {
            pioneerRewardActive[_pioneers[i]] = true;
            emit PioneerRewardActivated(_pioneers[i]);
        }

        // Initial state
        currentStage              = Stage.GREEN;
        oracleHealthy             = true;
        firstPublicPurchaseComplete = false;
        lastHeartbeat             = block.timestamp;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ORACLE FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    // ── Gold price — 5-oracle median consensus ────────────────────────────
    function getGoldPriceUSD() external view returns (uint256) {
        return OracleLib.getGoldPriceUSD(oracleAddresses);
    }

    // ── Silver price — Chainlink XAG/USD ─────────────────────────────────
    // Polygon Mainnet: 0x379589227b15F1a12195D3f2d90bBc9F31f95235
    function getSilverPriceUSD() external view returns (uint256) {
        return OracleLib.getSilverPriceUSD(silverUsdFeed);
    }

    // ── ETH/MATIC price — Chainlink ───────────────────────────────────────
    function getEthPriceUSD() external view returns (uint256) {
        (, int256 price, , uint256 updatedAt,) = ethUsdFeed.latestRoundData();
        require(price > 0, "Invalid ETH price");
        require(
            block.timestamp - updatedAt <= OracleLib.CHAINLINK_STALENESS,
            "ETH oracle stale"
        );
        return uint256(price) * 1e10; // 8 → 18 decimals
    }

    // ── Oracle health check (P-4 — replaces getBackingRatio) ─────────────
    function getOracleHealth() public view returns (
        bool chainlinkHealthy,
        uint256 responsiveOracles,
        bool systemHealthy
    ) {
        return OracleLib.getOracleHealth(ethUsdFeed, oracleAddresses);
    }

    // ── USD to Wei conversion ─────────────────────────────────────────────
    function usdToWei(uint256 usdAmount18) external view returns (uint256) {
        (, int256 price, , uint256 updatedAt,) = ethUsdFeed.latestRoundData();
        require(price > 0 && block.timestamp - updatedAt <= OracleLib.CHAINLINK_STALENESS);
        uint256 ethPrice = uint256(price) * 1e10;
        return (usdAmount18 * 1e18) / ethPrice;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // STAGE MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════

    // ── Auto-YELLOW on first public purchase (P-6) ────────────────────────
    function confirmFirstPublicPurchase() external onlyToken {
        if (!firstPublicPurchaseComplete && currentStage == Stage.GREEN) {
            firstPublicPurchaseComplete = true;
            currentStage = Stage.YELLOW;
            emit StageChanged(Stage.YELLOW, Stage.GREEN);
            emit FirstPublicPurchaseConfirmed(block.timestamp);
        }
    }

    // ── Manual YELLOW (backup — requires first purchase already happened) ─
    function transitionToYellow() external onlyFounderOrLegacy notLocked {
        require(currentStage == Stage.GREEN, "Not in GREEN");
        require(firstPublicPurchaseComplete, "No public purchase yet");
        currentStage = Stage.YELLOW;
        emit StageChanged(Stage.YELLOW, Stage.GREEN);
    }

    // ── Manual GOLD ───────────────────────────────────────────────────────
    function transitionToGold()
        external onlyFounderOrLegacy notLocked
        timelocked(keccak256("TRANSITION_GOLD"))
    {
        require(currentStage == Stage.YELLOW, "Not in YELLOW");
        currentStage = Stage.GOLD;
        emit StageChanged(Stage.GOLD, Stage.YELLOW);
    }

    // ── Manual BLUE — stops ALL pioneer rewards ───────────────────────────
    function transitionToBlue()
        external onlyFounderOrLegacy notLocked
        timelocked(keccak256("TRANSITION_BLUE"))
    {
        require(currentStage == Stage.GOLD, "Not in GOLD");
        currentStage = Stage.BLUE;

        // Deactivate all remaining pioneer rewards
        for (uint i = 0; i < 5; i++) {
            if (pioneerRewardActive[majorPioneerWallets[i]]) {
                pioneerRewardActive[majorPioneerWallets[i]] = false;
                emit PioneerRewardDeactivated(majorPioneerWallets[i], block.timestamp);
            }
        }

        emit StageChanged(Stage.BLUE, Stage.GOLD);
    }

    // ── Manual WHITE — bracelet launch ───────────────────────────────────
    function transitionToWhite()
        external onlyFounderOrLegacy notLocked
    {
        require(currentStage == Stage.BLUE, "Not in BLUE");
        currentStage = Stage.WHITE;
        emit StageChanged(Stage.WHITE, Stage.BLUE);
    }

    // ── Oracle health RED check (P-5 — replaces ratio check) ─────────────
    function checkRedStage() external {
        (, uint256 responsiveOracles, bool systemHealthy) = getOracleHealth();

        if (currentStage != Stage.RED && !systemHealthy) {
            _stageBeforeRed = currentStage;
            currentStage    = Stage.RED;
            oracleHealthy   = false;
            lastOracleHealthCheck = block.timestamp;
            emit StageChanged(Stage.RED, _stageBeforeRed);
            emit OracleFailureDetected(block.timestamp, responsiveOracles);
        }
        else if (currentStage == Stage.RED && systemHealthy) {
            currentStage   = _stageBeforeRed;
            oracleHealthy  = true;
            lastOracleHealthCheck = block.timestamp;
            emit StageChanged(_stageBeforeRed, Stage.RED);
            emit OracleRecovered(block.timestamp);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PIONEER REWARD SYSTEM (P-7)
    // ═══════════════════════════════════════════════════════════════════════

    // Called by token when pioneer pays first membership or first referral
    function deactivatePioneerReward(address pioneer) external onlyToken {
        if (pioneerRewardActive[pioneer]) {
            pioneerRewardActive[pioneer] = false;
            emit PioneerRewardDeactivated(pioneer, block.timestamp);
        }
    }

    function isPioneer(address addr) external view returns (bool) {
        for (uint i = 0; i < 5; i++) {
            if (majorPioneerWallets[i] == addr) return true;
        }
        return false;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // GUARDIAN SYSTEM
    // ═══════════════════════════════════════════════════════════════════════

    function approveGuardianPause() external onlyGuardian {
        require(!guardianPauseApproval[msg.sender], "Already approved");
        guardianPauseApproval[msg.sender] = true;
        pauseApprovalCount++;
        emit GuardianPauseApproved(msg.sender);

        if (GuardianLib.isPauseApprovalThresholdMet(pauseApprovalCount)) {
            _pause();
            // Reset approvals
            for (uint i = 0; i < 3; i++) {
                guardianPauseApproval[guardians[i]] = false;
            }
            pauseApprovalCount = 0;
        }
    }

    function guardianUnpause() external onlyOwner {
        _unpause();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // DEAD-MAN SWITCH
    // ═══════════════════════════════════════════════════════════════════════

    function heartbeat() external onlyFounderOrLegacy {
        lastHeartbeat = block.timestamp;
        emit HeartbeatReceived(block.timestamp);
    }

    function triggerDeadManSwitch() external onlyGuardian {
        require(DeadManLib.isHeartbeatExpired(lastHeartbeat), "Heartbeat still active");
        require(!deadManActive, "Already active");
        deadManActive = true;
        systemLocked  = true;
        emit DeadManTriggered(block.timestamp);
    }

    function submitDeathProof(
        uint8 proofType, // 0=family, 1=company, 2=thirdParty
        bytes32 proofHash
    ) external onlyGuardian {
        require(deadManActive, "Dead-man not active");
        bytes32 proofId = DeadManLib.getProofId(proofType, proofHash);
        deathProofSubmitted[proofId] = true;

        if (proofType == 0) familyProofId    = proofId;
        if (proofType == 1) companyProofId   = proofId;
        if (proofType == 2) thirdPartyProofId = proofId;

        emit DeathProofSubmitted(msg.sender, block.timestamp);

        // Check if all 3 proofs are in
        if (DeadManLib.allProofsSubmitted(familyProofId, companyProofId, thirdPartyProofId, deathProofSubmitted)) {
            _activateLegacyMode();
        }
    }

    function _activateLegacyMode() internal {
        legacyModeActive = true;
        emit LegacyModeActivated(legacyWallet);
    }

    function setLegacyWallet(address _legacy)
        external onlyFounderOrLegacy
        timelocked(keccak256("SET_LEGACY_WALLET"))
    {
        legacyWallet = _legacy;
    }

    // ── Pioneer resurrection — 3-of-5 pioneers approve ───────────────────
    function approvePioneerResurrection() external {
        bool isPioneerAddr = false;
        for (uint i = 0; i < 5; i++) {
            if (majorPioneerWallets[i] == msg.sender) {
                isPioneerAddr = true;
                break;
            }
        }
        require(isPioneerAddr, "Not a pioneer");
        require(!hasApprovedResurrection[msg.sender], "Already approved");
        require(deadManActive, "Dead-man not active");

        hasApprovedResurrection[msg.sender] = true;
        resurrectionApprovalCount++;
        emit ResurrectionApproved(msg.sender);

        if (resurrectionApprovalCount >= 3) {
            deadManActive = false;
            systemLocked  = false;
            legacyModeActive = false;
            lastHeartbeat = block.timestamp;
            resurrectionApprovalCount = 0;

            // Reset approvals
            for (uint i = 0; i < 5; i++) {
                hasApprovedResurrection[majorPioneerWallets[i]] = false;
            }

            emit Resurrected(msg.sender, block.timestamp);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ADMIN — WALLET SETTERS (all timelocked)
    // ═══════════════════════════════════════════════════════════════════════

    function setFounderWallet(address w)
        external onlyOwner timelocked(keccak256("SET_FOUNDER"))
    {
        require(w != address(0));
        founderWallet = w;
        emit WalletUpdated("founder", w);
    }

    function setGoldReserveWallet(address w)
        external onlyOwner timelocked(keccak256("SET_GOLD_RESERVE"))
    {
        require(w != address(0));
        goldReserveWallet = w;
        emit WalletUpdated("goldReserve", w);
    }

    function setSilverReserveWallet(address w)
        external onlyOwner timelocked(keccak256("SET_SILVER_RESERVE"))
    {
        require(w != address(0));
        silverReserveWallet = w;
        emit WalletUpdated("silverReserve", w);
    }

    function setOperationsWallet(address w)
        external onlyOwner timelocked(keccak256("SET_OPERATIONS"))
    {
        require(w != address(0));
        operationsWallet = w;
        emit WalletUpdated("operations", w);
    }

    function setGoldTokenContract(address t) external onlyOwner {
        require(goldTokenContract == address(0), "Already set");
        goldTokenContract = t;
    }

    function setSilverTokenContract(address t) external onlyOwner {
        require(silverTokenContract == address(0), "Already set");
        silverTokenContract = t;
    }

    function setNFTContract(address n) external onlyOwner {
        nftContract = n;
    }

    function setOracleAddress(uint8 index, address oracle)
        external onlyOwner timelocked(keccak256(abi.encode("SET_ORACLE", index)))
    {
        require(index < 5);
        oracleAddresses[index] = oracle;
        emit OracleAddressUpdated(index, oracle);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // UUPS UPGRADE
    // ═══════════════════════════════════════════════════════════════════════

    function _authorizeUpgrade(address newImpl)
        internal override onlyOwner {}
}
