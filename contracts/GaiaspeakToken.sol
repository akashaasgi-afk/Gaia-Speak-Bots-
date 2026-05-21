// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/ReentrancyGuardUpgradeable.sol";
import "./libraries/TokenLib.sol";

// ═══════════════════════════════════════════════════════════════════════════
// INTERFACE — Protocol
// ═══════════════════════════════════════════════════════════════════════════

interface IGaiaSpeakProtocol {
    enum Stage { GREEN, YELLOW, GOLD, BLUE, RED, WHITE }

    function currentStage()               external view returns (Stage);
    function founderWallet()              external view returns (address);
    function goldReserveWallet()          external view returns (address);
    function operationsWallet()           external view returns (address);
    function referralWallet()             external view returns (address);
    function majorPioneerWallets(uint256) external view returns (address);
    function pioneerRewardActive(address) external view returns (bool);
    function oracleHealthy()              external view returns (bool);

    function getGoldPriceUSD()  external view returns (uint256);
    function getEthPriceUSD()   external view returns (uint256);
    function usdToWei(uint256)  external view returns (uint256);

    function confirmFirstPublicPurchase() external;
    function deactivatePioneerReward(address pioneer) external;
    function isPioneer(address)           external view returns (bool);
}

// ═══════════════════════════════════════════════════════════════════════════
// GAIASPEAK TOKEN (GSG) — GaiaSpeak Gold
// Changes from v1:
//   T-1: Removed fixed tier pricing — oracle price per gram, live
//   T-2: Added fractional minting — any amount ≥ $1 buys fraction of gram
//   T-3: Auto-YELLOW trigger on first public purchase
//   T-4: Pioneer auto-deactivation on first membership or referral claim
//   T-5: Annual membership option — 365 days for price of 10 months
//   T-6: redeemPhysical → requestPhysicalDelivery (PAXG integration, same-block protection)
// ═══════════════════════════════════════════════════════════════════════════

contract GaiaSpeakToken is
    ERC20Upgradeable,
    UUPSUpgradeable,
    OwnableUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable
{
    IGaiaSpeakProtocol public protocol;

    // ─── FLASH LOAN PROTECTION (T-2) ─────────────────────────────────────
    mapping(address => uint256) private _lastPurchaseBlock;
    mapping(address => uint256) private _lastActionTime;

    // ─── MEMBERSHIP (T-5) ─────────────────────────────────────────────────
    mapping(address => uint256) public membershipExpiry;
    uint256 public monthlyMembershipPrice; // in Wei
    uint256 public annualMembershipPrice;  // = monthlyPrice × 10

    // ─── REFERRAL SYSTEM ─────────────────────────────────────────────────
    mapping(address => address) public referredBy;
    mapping(address => uint256) public referralCount;      // completed purchases
    mapping(address => uint256) public referralRewardsPending;

    // ─── TRANSFER FEES ────────────────────────────────────────────────────
    mapping(address => bool) public feeExempt;

    // ─── EVENTS ───────────────────────────────────────────────────────────
    event GoldPurchased(
        address indexed buyer,
        uint256 weiSent,
        uint256 gramsMinted,
        uint256 goldPriceUSD
    );
    event PhysicalDeliveryRequested(
        address indexed requester,
        uint256 gsAmount,
        string  deliveryInfo,
        uint256 timestamp
    );
    event CashRedemption(
        address indexed redeemer,
        uint256 gsAmount,
        uint256 usdcValue
    );
    event MembershipPurchased(
        address indexed member,
        bool    annual,
        uint256 expiry
    );
    event ReferralRecorded(address indexed referrer, address indexed buyer);
    event ReferralRewardEarned(address indexed referrer, uint256 gsAmount);
    event PioneerTransitionedToMember(address indexed pioneer, uint256 timestamp);
    event TokensBurned(address indexed from, uint256 amount);

    // ═══════════════════════════════════════════════════════════════════════
    // MODIFIERS
    // ═══════════════════════════════════════════════════════════════════════

    modifier notRedStage() {
        require(
            protocol.currentStage() != IGaiaSpeakProtocol.Stage.RED,
            "Protocol in RED stage - purchases suspended"
        );
        _;
    }

    modifier notLocked() {
        require(protocol.oracleHealthy(), "Oracle unhealthy");
        _;
    }

    modifier rateLimited() {
        require(
            TokenLib.isCooldownExpired(_lastActionTime[msg.sender]),
            "Please wait 60 seconds between purchases"
        );
        _lastActionTime[msg.sender] = block.timestamp;
        _;
    }

    modifier noFlashLoan() {
        require(
            block.number > _lastPurchaseBlock[msg.sender],
            "Cannot buy and redeem in same block"
        );
        _;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZER
    // ═══════════════════════════════════════════════════════════════════════

    function initialize(
        address _protocol,
        uint256 _monthlyMembershipWei,
        string memory name,
        string memory symbol
    ) external initializer {
        __ERC20_init(name, symbol);
        __Ownable_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        __UUPSUpgradeable_init();

        protocol = IGaiaSpeakProtocol(_protocol);
        monthlyMembershipPrice = _monthlyMembershipWei;
        annualMembershipPrice  = _monthlyMembershipWei * 10; // 12 months for price of 10

        // Fee exemptions for system wallets
        feeExempt[_protocol] = true;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PURCHASE — T-1, T-2, T-3
    // Fractional gram minting at live oracle price
    // Any amount ≥ $1.00 buys proportional fraction
    // ═══════════════════════════════════════════════════════════════════════

    function purchaseTokens(address referrer)
        external payable
        nonReentrant
        whenNotPaused
        notRedStage
        rateLimited
    {
        // ── Oracle price (T-1: replaces fixed $7.77) ─────────────────────
        uint256 goldPricePerGram = protocol.getGoldPriceUSD(); // 18 decimals
        require(goldPricePerGram > 0, "Gold oracle unavailable");

        uint256 ethPriceUSD = protocol.getEthPriceUSD(); // 18 decimals
        require(ethPriceUSD > 0, "ETH oracle unavailable");

        // Convert MATIC sent → USD value (18 decimals)
        uint256 sentUSD = (msg.value * ethPriceUSD) / 1e18;

        // ── Minimum $1.00 check (T-2) ────────────────────────────────────
        require(
            TokenLib.meetsMinimumPurchase(sentUSD),
            "Minimum purchase is $1.00"
        );

        // ── Flash loan protection (T-2) ──────────────────────────────────
        _lastPurchaseBlock[msg.sender] = block.number;

        // ── Fractional gram calculation (T-2) ────────────────────────────
        // gsAmount in 18 decimals = grams of gold
        // sentUSD / goldPricePerGram = grams purchased
        uint256 gsAmount = TokenLib.calculateGramAmount(sentUSD, goldPricePerGram);
        require(gsAmount > 0, "Amount too small to mint");

        // ── Auto-YELLOW on first public purchase (T-3) ───────────────────
        // Pioneers buying in GREEN do not trigger YELLOW
        bool isBuyerPioneer = protocol.isPioneer(msg.sender);
        if (!isBuyerPioneer &&
            protocol.currentStage() == IGaiaSpeakProtocol.Stage.GREEN)
        {
            protocol.confirmFirstPublicPurchase();
        }

        // ── Referral tracking ────────────────────────────────────────────
        if (referrer != address(0) &&
            referrer != msg.sender &&
            referredBy[msg.sender] == address(0))
        {
            referredBy[msg.sender] = referrer;
        }
        if (referredBy[msg.sender] != address(0)) {
            _recordReferral(referredBy[msg.sender]);
        }

        // ── Mint tokens ──────────────────────────────────────────────────
        _mint(msg.sender, gsAmount);

        // ── Distribute funds ─────────────────────────────────────────────
        _distributeFunds(msg.value);

        emit GoldPurchased(msg.sender, msg.value, gsAmount, goldPricePerGram);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUND DISTRIBUTION
    // Percentages are SACRED — do not change
    // Pioneer 0.01% only paid when pioneerRewardActive == true (T-4)
    // Inactive pioneer shares flow to reserve
    // ═══════════════════════════════════════════════════════════════════════

    function _distributeFunds(uint256 amount) internal {
        IGaiaSpeakProtocol.Stage stage = protocol.currentStage();

        if (stage == IGaiaSpeakProtocol.Stage.GREEN ||
            stage == IGaiaSpeakProtocol.Stage.YELLOW ||
            stage == IGaiaSpeakProtocol.Stage.BLUE   ||
            stage == IGaiaSpeakProtocol.Stage.WHITE)
        {
            // GREEN/YELLOW/BLUE/WHITE distribution via TokenLib constants
            uint256 founderShare  = TokenLib.calculateFee(amount, TokenLib.FOUNDER_SHARE_BPS);
            uint256 pioneerTotal  = TokenLib.calculateFee(amount, TokenLib.PIONEER_TOTAL_BPS);
            uint256 reserveShare  = TokenLib.calculateFee(amount, TokenLib.RESERVE_SHARE_BPS);
            uint256 opsShare      = TokenLib.calculateFee(amount, TokenLib.OPERATIONS_SHARE_BPS);

            // Dust goes to reserve (rounding protection)
            uint256 distributed = founderShare + pioneerTotal + reserveShare + opsShare;
            if (distributed < amount) {
                reserveShare += amount - distributed;
            }

            // Send founder
            _sendETH(protocol.founderWallet(), founderShare);

            // Pioneer distribution — only active pioneers receive (T-4)
            uint256 actualPioneerPaid = 0;
            uint256 perPioneer = pioneerTotal / 5;
            for (uint i = 0; i < 5; i++) {
                address pioneer = protocol.majorPioneerWallets(i);
                if (protocol.pioneerRewardActive(pioneer) &&
                    stage != IGaiaSpeakProtocol.Stage.YELLOW // YELLOW: pioneer 0.01% stopped
                ) {
                    _sendETH(pioneer, perPioneer);
                    actualPioneerPaid += perPioneer;
                }
            }
            // Unused pioneer shares → reserve
            uint256 unusedPioneer = pioneerTotal - actualPioneerPaid;
            reserveShare += unusedPioneer;

            _sendETH(protocol.goldReserveWallet(), reserveShare);
            _sendETH(protocol.operationsWallet(), opsShare);

        } else if (stage == IGaiaSpeakProtocol.Stage.GOLD) {
            // GOLD stage: user pays spot + 5% markup
            // Spot portion → reserve
            // Markup: 40% founder, 60% reserve
            uint256 goldPriceWei = protocol.usdToWei(protocol.getGoldPriceUSD());
            uint256 markup = amount - goldPriceWei;
            if (markup > 0) {
                uint256 founderMarkup  = (markup * TokenLib.GOLD_FOUNDER_MARKUP_PCT) / 100;
                uint256 reserveMarkup  = markup - founderMarkup;
                _sendETH(protocol.founderWallet(), founderMarkup);
                _sendETH(protocol.goldReserveWallet(), goldPriceWei + reserveMarkup);
            } else {
                _sendETH(protocol.goldReserveWallet(), amount);
            }
        }
    }

    function _sendETH(address to, uint256 amount) internal {
        if (amount == 0 || to == address(0)) return;
        (bool ok,) = payable(to).call{value: amount}("");
        require(ok, "ETH transfer failed");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MEMBERSHIP PASS (T-5)
    // Monthly OR annual — annual = 12 months for price of 10
    // ═══════════════════════════════════════════════════════════════════════

    function purchaseMembership(bool annual)
        external payable
        nonReentrant
        whenNotPaused
    {
        // ── Pioneer auto-deactivation (T-4) ──────────────────────────────
        _checkAndDeactivatePioneerReward(msg.sender);

        uint256 price    = annual ? annualMembershipPrice : monthlyMembershipPrice;
        uint256 duration = TokenLib.getMembershipDuration(annual);

        require(msg.value >= price, "Insufficient membership payment");

        // Extend existing membership or start fresh
        uint256 currentExpiry = membershipExpiry[msg.sender];
        if (currentExpiry > block.timestamp) {
            membershipExpiry[msg.sender] = currentExpiry + duration;
        } else {
            membershipExpiry[msg.sender] = block.timestamp + duration;
        }

        // Distribute membership fees to operations
        _sendETH(protocol.operationsWallet(), msg.value);

        emit MembershipPurchased(msg.sender, annual, membershipExpiry[msg.sender]);
    }

    function isMember(address user) public view returns (bool) {
        return TokenLib.isMember(membershipExpiry[user]);
    }

    // ── Pioneer auto-deactivation helper (T-4) ────────────────────────────
    function _checkAndDeactivatePioneerReward(address user) internal {
        if (protocol.isPioneer(user) && protocol.pioneerRewardActive(user)) {
            protocol.deactivatePioneerReward(user);
            emit PioneerTransitionedToMember(user, block.timestamp);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // REFERRAL SYSTEM
    // 10 completed referral purchases = 1 GSG token reward
    // ═══════════════════════════════════════════════════════════════════════

    function _recordReferral(address referrer) internal {
        referralCount[referrer]++;
        emit ReferralRecorded(referrer, msg.sender);

        if (TokenLib.hasReferralReward(referralCount[referrer])) {
            referralRewardsPending[referrer]++;
        }
    }

    function claimReferralRewards() external nonReentrant whenNotPaused {
        // ── Pioneer auto-deactivation (T-4) ──────────────────────────────
        _checkAndDeactivatePioneerReward(msg.sender);

        uint256 pending = referralRewardsPending[msg.sender];
        require(pending > 0, "No referral rewards pending");

        referralRewardsPending[msg.sender] = 0;

        // Mint 1 GSG per reward earned (at 1 full gram = 1e18)
        uint256 rewardAmount = pending * 1e18;
        _mint(msg.sender, rewardAmount);

        emit ReferralRewardEarned(msg.sender, rewardAmount);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // REDEMPTION — T-6
    // Renamed from redeemPhysical → requestPhysicalDelivery
    // Honest naming: GaiaSpeak submits request, fulfilled off-chain via PAXG
    // ═══════════════════════════════════════════════════════════════════════

    function requestPhysicalDelivery(
        uint256 gsAmount,
        string calldata deliveryInfo // encrypted off-chain
    ) external nonReentrant whenNotPaused noFlashLoan {
        require(gsAmount >= 1e18, "Minimum 1 full gram for physical delivery");
        require(balanceOf(msg.sender) >= gsAmount, "Insufficient GSG balance");
        require(
            protocol.currentStage() != IGaiaSpeakProtocol.Stage.RED,
            "Delivery unavailable during RED stage"
        );

        _burn(msg.sender, gsAmount);

        // Off-chain system picks up this event and fulfils via PAXG or dealer
        emit PhysicalDeliveryRequested(
            msg.sender,
            gsAmount,
            deliveryInfo,
            block.timestamp
        );
        emit TokensBurned(msg.sender, gsAmount);
    }

    // ── USDC redemption ───────────────────────────────────────────────────
    function redeemForUSDC(uint256 gsAmount)
        external nonReentrant whenNotPaused noFlashLoan
    {
        require(gsAmount >= 1e18, "Minimum 1 gram");
        require(balanceOf(msg.sender) >= gsAmount, "Insufficient balance");

        _burn(msg.sender, gsAmount);

        // Emit event — fulfilled off-chain
        uint256 goldPriceUSD = protocol.getGoldPriceUSD();
        uint256 usdcValue = (gsAmount * goldPriceUSD) / 1e18;

        emit CashRedemption(msg.sender, gsAmount, usdcValue);
        emit TokensBurned(msg.sender, gsAmount);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TRANSFER FEE SYSTEM (unchanged from v1)
    // External: 2% (1% ops, 1% reserve)
    // P2P member-to-member: 0.02% (50% burn, 50% reserve)
    // Minimum transfer: 0.5 GSG
    // ═══════════════════════════════════════════════════════════════════════

    function _transfer(
        address from,
        address to,
        uint256 amount
    ) internal override {
        // Skip fee on mint/burn or exempt addresses
        if (from == address(0) || to == address(0) ||
            feeExempt[from] || feeExempt[to])
        {
            super._transfer(from, to, amount);
            return;
        }

        require(amount >= TokenLib.MIN_TRANSFER_TOKENS, "Below minimum transfer");

        bool fromMember = isMember(from);
        bool toMember   = isMember(to);

        uint256 fee;
        uint256 burnAmount;

        if (fromMember && toMember) {
            // P2P member-to-member: 0.02%
            fee = TokenLib.calculateFee(amount, TokenLib.P2P_FEE_BPS);
            burnAmount = fee / 2;
            uint256 reserveFee = fee - burnAmount;
            super._burn(from, burnAmount);
            super._transfer(from, protocol.goldReserveWallet(), reserveFee);
        } else {
            // External transfer: 2%
            fee = TokenLib.calculateFee(amount, TokenLib.EXTERNAL_FEE_BPS);
            uint256 half = fee / 2;
            super._transfer(from, protocol.operationsWallet(), half);
            super._transfer(from, protocol.goldReserveWallet(), fee - half);
        }

        super._transfer(from, to, amount - fee);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ADMIN
    // ═══════════════════════════════════════════════════════════════════════

    function setFeeExempt(address addr, bool exempt) external onlyOwner {
        feeExempt[addr] = exempt;
    }

    function setMembershipPrices(
        uint256 monthly,
        uint256 annual
    ) external onlyOwner {
        monthlyMembershipPrice = monthly;
        annualMembershipPrice  = annual;
    }

    function pause()   external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    function _authorizeUpgrade(address) internal override onlyOwner {}
}
