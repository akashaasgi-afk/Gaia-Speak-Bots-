// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/ReentrancyGuardUpgradeable.sol";
import "./libraries/TokenLib.sol";

// ═══════════════════════════════════════════════════════════════════════════
// INTERFACE — Protocol (same as gold token)
// ═══════════════════════════════════════════════════════════════════════════

interface IGaiaSpeakProtocolSilver {
    enum Stage { GREEN, YELLOW, GOLD, BLUE, RED, WHITE }

    function currentStage()               external view returns (Stage);
    function founderWallet()              external view returns (address);
    function silverReserveWallet()        external view returns (address); // DIFFERENCE 1 of 3 — silver reserve
    function operationsWallet()           external view returns (address);
    function referralWallet()             external view returns (address);
    function majorPioneerWallets(uint256) external view returns (address);
    function pioneerRewardActive(address) external view returns (bool);
    function oracleHealthy()              external view returns (bool);

    function getSilverPriceUSD() external view returns (uint256); // DIFFERENCE 2 of 3 — silver oracle
    function getEthPriceUSD()    external view returns (uint256);
    function usdToWei(uint256)   external view returns (uint256);

    function confirmFirstPublicPurchase() external;
    function deactivatePioneerReward(address pioneer) external;
    function isPioneer(address) external view returns (bool);
}

// ═══════════════════════════════════════════════════════════════════════════
// GAIASPEAK SILVER TOKEN (GSS) — GaiaSpeak Silver      DIFFERENCE 3 of 3
// Identical to GaiaSpeakToken.sol with exactly 3 differences:
//   1. Token name: "GaiaSpeak Silver" / symbol: "GSS"
//   2. Oracle: getSilverPriceUSD() instead of getGoldPriceUSD()
//   3. Reserve wallet: silverReserveWallet instead of goldReserveWallet
// Everything else — distribution, fees, referrals, membership,
// redemption, security, guardian integration — IDENTICAL
// ═══════════════════════════════════════════════════════════════════════════

contract GaiaSpeakSilverToken is
    ERC20Upgradeable,
    UUPSUpgradeable,
    OwnableUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable
{
    IGaiaSpeakProtocolSilver public protocol;

    mapping(address => uint256) private _lastPurchaseBlock;
    mapping(address => uint256) private _lastActionTime;

    mapping(address => uint256) public membershipExpiry;
    uint256 public monthlyMembershipPrice;
    uint256 public annualMembershipPrice;

    mapping(address => address) public referredBy;
    mapping(address => uint256) public referralCount;
    mapping(address => uint256) public referralRewardsPending;

    mapping(address => bool) public feeExempt;

    // ─── EVENTS ───────────────────────────────────────────────────────────
    event SilverPurchased(
        address indexed buyer,
        uint256 weiSent,
        uint256 gramsMinted,
        uint256 silverPriceUSD
    );
    event PhysicalDeliveryRequested(
        address indexed requester,
        uint256 gssAmount,
        string  deliveryInfo,
        uint256 timestamp
    );
    event CashRedemption(address indexed redeemer, uint256 gssAmount, uint256 usdcValue);
    event MembershipPurchased(address indexed member, bool annual, uint256 expiry);
    event ReferralRecorded(address indexed referrer, address indexed buyer);
    event ReferralRewardEarned(address indexed referrer, uint256 gssAmount);
    event PioneerTransitionedToMember(address indexed pioneer, uint256 timestamp);
    event TokensBurned(address indexed from, uint256 amount);

    // ═══════════════════════════════════════════════════════════════════════
    // MODIFIERS — identical to gold token
    // ═══════════════════════════════════════════════════════════════════════

    modifier notRedStage() {
        require(
            protocol.currentStage() != IGaiaSpeakProtocolSilver.Stage.RED,
            "Protocol in RED stage - purchases suspended"
        );
        _;
    }

    modifier rateLimited() {
        require(
            TokenLib.isCooldownExpired(_lastActionTime[msg.sender]),
            "Please wait 60 seconds"
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
        uint256 _monthlyMembershipWei
    ) external initializer {
        // DIFFERENCE — name and symbol
        __ERC20_init("GaiaSpeak Silver", "GSS");
        __Ownable_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        __UUPSUpgradeable_init();

        protocol = IGaiaSpeakProtocolSilver(_protocol);
        monthlyMembershipPrice = _monthlyMembershipWei;
        annualMembershipPrice  = _monthlyMembershipWei * 10;

        feeExempt[_protocol] = true;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PURCHASE — uses silver oracle (DIFFERENCE)
    // ═══════════════════════════════════════════════════════════════════════

    function purchaseTokens(address referrer)
        external payable
        nonReentrant
        whenNotPaused
        notRedStage
        rateLimited
    {
        // DIFFERENCE — getSilverPriceUSD instead of getGoldPriceUSD
        uint256 silverPricePerGram = protocol.getSilverPriceUSD();
        require(silverPricePerGram > 0, "Silver oracle unavailable");

        uint256 ethPriceUSD = protocol.getEthPriceUSD();
        require(ethPriceUSD > 0, "ETH oracle unavailable");

        uint256 sentUSD = (msg.value * ethPriceUSD) / 1e18;
        require(
            TokenLib.meetsMinimumPurchase(sentUSD),
            "Minimum purchase is $1.00"
        );

        _lastPurchaseBlock[msg.sender] = block.number;

        uint256 gssAmount = TokenLib.calculateGramAmount(sentUSD, silverPricePerGram);
        require(gssAmount > 0, "Amount too small");

        bool isBuyerPioneer = protocol.isPioneer(msg.sender);
        if (!isBuyerPioneer &&
            protocol.currentStage() == IGaiaSpeakProtocolSilver.Stage.GREEN)
        {
            protocol.confirmFirstPublicPurchase();
        }

        if (referrer != address(0) &&
            referrer != msg.sender &&
            referredBy[msg.sender] == address(0))
        {
            referredBy[msg.sender] = referrer;
        }
        if (referredBy[msg.sender] != address(0)) {
            _recordReferral(referredBy[msg.sender]);
        }

        _mint(msg.sender, gssAmount);
        _distributeFunds(msg.value);

        emit SilverPurchased(msg.sender, msg.value, gssAmount, silverPricePerGram);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUND DISTRIBUTION — uses silverReserveWallet (DIFFERENCE)
    // All percentages IDENTICAL to gold token
    // ═══════════════════════════════════════════════════════════════════════

    function _distributeFunds(uint256 amount) internal {
        IGaiaSpeakProtocolSilver.Stage stage = protocol.currentStage();

        if (stage != IGaiaSpeakProtocolSilver.Stage.GOLD) {
            uint256 founderShare = TokenLib.calculateFee(amount, TokenLib.FOUNDER_SHARE_BPS);
            uint256 pioneerTotal = TokenLib.calculateFee(amount, TokenLib.PIONEER_TOTAL_BPS);
            uint256 reserveShare = TokenLib.calculateFee(amount, TokenLib.RESERVE_SHARE_BPS);
            uint256 opsShare     = TokenLib.calculateFee(amount, TokenLib.OPERATIONS_SHARE_BPS);

            uint256 distributed = founderShare + pioneerTotal + reserveShare + opsShare;
            if (distributed < amount) reserveShare += amount - distributed;

            _sendETH(protocol.founderWallet(), founderShare);

            uint256 actualPioneerPaid = 0;
            uint256 perPioneer = pioneerTotal / 5;
            for (uint i = 0; i < 5; i++) {
                address pioneer = protocol.majorPioneerWallets(i);
                if (protocol.pioneerRewardActive(pioneer) &&
                    stage != IGaiaSpeakProtocolSilver.Stage.YELLOW)
                {
                    _sendETH(pioneer, perPioneer);
                    actualPioneerPaid += perPioneer;
                }
            }
            reserveShare += pioneerTotal - actualPioneerPaid;

            // DIFFERENCE — silverReserveWallet
            _sendETH(protocol.silverReserveWallet(), reserveShare);
            _sendETH(protocol.operationsWallet(), opsShare);

        } else {
            // GOLD stage — spot + 5% markup
            uint256 silverPriceWei = protocol.usdToWei(protocol.getSilverPriceUSD());
            uint256 markup = amount > silverPriceWei ? amount - silverPriceWei : 0;
            if (markup > 0) {
                uint256 founderMarkup = (markup * TokenLib.GOLD_FOUNDER_MARKUP_PCT) / 100;
                _sendETH(protocol.founderWallet(), founderMarkup);
                _sendETH(protocol.silverReserveWallet(), silverPriceWei + markup - founderMarkup);
            } else {
                _sendETH(protocol.silverReserveWallet(), amount);
            }
        }
    }

    function _sendETH(address to, uint256 amount) internal {
        if (amount == 0 || to == address(0)) return;
        (bool ok,) = payable(to).call{value: amount}("");
        require(ok, "ETH transfer failed");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MEMBERSHIP, REFERRALS, REDEMPTION — IDENTICAL to gold token
    // ═══════════════════════════════════════════════════════════════════════

    function purchaseMembership(bool annual)
        external payable nonReentrant whenNotPaused
    {
        _checkAndDeactivatePioneerReward(msg.sender);
        uint256 price    = annual ? annualMembershipPrice : monthlyMembershipPrice;
        uint256 duration = TokenLib.getMembershipDuration(annual);
        require(msg.value >= price, "Insufficient payment");

        uint256 currentExpiry = membershipExpiry[msg.sender];
        if (currentExpiry > block.timestamp) {
            membershipExpiry[msg.sender] = currentExpiry + duration;
        } else {
            membershipExpiry[msg.sender] = block.timestamp + duration;
        }
        _sendETH(protocol.operationsWallet(), msg.value);
        emit MembershipPurchased(msg.sender, annual, membershipExpiry[msg.sender]);
    }

    function isMember(address user) public view returns (bool) {
        return TokenLib.isMember(membershipExpiry[user]);
    }

    function _checkAndDeactivatePioneerReward(address user) internal {
        if (protocol.isPioneer(user) && protocol.pioneerRewardActive(user)) {
            protocol.deactivatePioneerReward(user);
            emit PioneerTransitionedToMember(user, block.timestamp);
        }
    }

    function _recordReferral(address referrer) internal {
        referralCount[referrer]++;
        emit ReferralRecorded(referrer, msg.sender);
        if (TokenLib.hasReferralReward(referralCount[referrer])) {
            referralRewardsPending[referrer]++;
        }
    }

    function claimReferralRewards() external nonReentrant whenNotPaused {
        _checkAndDeactivatePioneerReward(msg.sender);
        uint256 pending = referralRewardsPending[msg.sender];
        require(pending > 0, "No rewards pending");
        referralRewardsPending[msg.sender] = 0;
        uint256 rewardAmount = pending * 1e18;
        _mint(msg.sender, rewardAmount);
        emit ReferralRewardEarned(msg.sender, rewardAmount);
    }

    function requestPhysicalDelivery(uint256 gssAmount, string calldata deliveryInfo)
        external nonReentrant whenNotPaused noFlashLoan
    {
        require(gssAmount >= 1e18, "Minimum 1 full gram");
        require(balanceOf(msg.sender) >= gssAmount, "Insufficient GSS");
        require(
            protocol.currentStage() != IGaiaSpeakProtocolSilver.Stage.RED,
            "Unavailable during RED"
        );
        _burn(msg.sender, gssAmount);
        emit PhysicalDeliveryRequested(msg.sender, gssAmount, deliveryInfo, block.timestamp);
        emit TokensBurned(msg.sender, gssAmount);
    }

    function redeemForUSDC(uint256 gssAmount)
        external nonReentrant whenNotPaused noFlashLoan
    {
        require(gssAmount >= 1e18, "Minimum 1 gram");
        require(balanceOf(msg.sender) >= gssAmount, "Insufficient balance");
        _burn(msg.sender, gssAmount);
        uint256 silverPriceUSD = protocol.getSilverPriceUSD();
        uint256 usdcValue = (gssAmount * silverPriceUSD) / 1e18;
        emit CashRedemption(msg.sender, gssAmount, usdcValue);
        emit TokensBurned(msg.sender, gssAmount);
    }

    // ─── Transfer fee — identical to gold ────────────────────────────────
    function _transfer(address from, address to, uint256 amount) internal override {
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

        if (fromMember && toMember) {
            fee = TokenLib.calculateFee(amount, TokenLib.P2P_FEE_BPS);
            uint256 burnAmt = fee / 2;
            super._burn(from, burnAmt);
            super._transfer(from, protocol.silverReserveWallet(), fee - burnAmt);
        } else {
            fee = TokenLib.calculateFee(amount, TokenLib.EXTERNAL_FEE_BPS);
            uint256 half = fee / 2;
            super._transfer(from, protocol.operationsWallet(), half);
            super._transfer(from, protocol.silverReserveWallet(), fee - half);
        }
        super._transfer(from, to, amount - fee);
    }

    function setFeeExempt(address addr, bool exempt) external onlyOwner {
        feeExempt[addr] = exempt;
    }

    function setMembershipPrices(uint256 monthly, uint256 annual) external onlyOwner {
        monthlyMembershipPrice = monthly;
        annualMembershipPrice  = annual;
    }

    function pause()   external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }
    function _authorizeUpgrade(address) internal override onlyOwner {}
}
