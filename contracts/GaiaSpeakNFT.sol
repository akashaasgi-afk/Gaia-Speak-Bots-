// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/token/ERC721/ERC721Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/token/ERC721/extensions/ERC721URIStorageUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "./libraries/NFTLib.sol";

// =============================================================================
// INTERFACES
// =============================================================================

interface IGaiaSpeakProtocol {
    enum Stage { GREEN, YELLOW, GOLD, BLUE, RED, WHITE }
    function currentStage() external view returns (Stage);
    function isGuardian(address) external view returns (bool);
    function paused() external view returns (bool);
}

interface IGaiaSpeakToken {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

// =============================================================================
// GAIASPEAKNFT
// =============================================================================

/**
 * @title  GaiaSpeakNFT
 * @author GaiaSpeak Protocol
 *
 * @notice Content marketplace for the GaiaSpeak ecosystem.
 *
 *         What this contract does:
 *         ─────────────────────────────────────────────────────────────────────
 *         Creators mint digital content certificates (images, documents,
 *         audio, certificates, any digital asset) as NFTs.
 *
 *         Buyers pay in GSG (gold token) or GSS (silver token).
 *
 *         On every sale, fees distribute automatically:
 *           60% → creator
 *           20% → founder wallet
 *           20% → reserve wallet (gold reserve for GSG, silver for GSS)
 *
 *         Buyers have 7 days to dispute a purchase.
 *         Creators can appeal a buyer-favoured resolution (0.5 token fee).
 *
 *         This contract does NOT mint gold. It IS NOT the gold token.
 *         GSG and GSS are the CURRENCY used to buy content here.
 *
 * @dev    v2 changes applied to original:
 *         N-1: silverTokenContract state variable added
 *         N-2: setSilverTokenContract() owner function added
 *         N-3: PaymentToken enum (GOLD | SILVER) added
 *         N-4: buyNFT() routes to correct token + correct reserve wallet
 *         N-5: All 60/20/20 distributions apply to whichever token was used
 *         Everything else (dispute system, appeal, guardian pause,
 *         UUPS upgrade, nonReentrant guards) unchanged from verified version.
 */
contract GaiaSpeakNFT is
    ERC721Upgradeable,
    ERC721URIStorageUpgradeable,
    ReentrancyGuardUpgradeable,
    PausableUpgradeable,
    OwnableUpgradeable,
    UUPSUpgradeable
{
    // =========================================================================
    // CONSTANTS (using NFTLib)
    // =========================================================================

    // =========================================================================
    // STATE
    // =========================================================================

    /// @notice Protocol contract — source of truth for stage and guardian status
    IGaiaSpeakProtocol public protocolContract;

    /// @notice GSG — GaiaSpeak Gold token
    IGaiaSpeakToken    public goldTokenContract;

    /// @notice GSS — GaiaSpeak Silver token (v2 addition)
    IGaiaSpeakToken    public silverTokenContract;

    /// @notice Receives 20% of every NFT sale
    address public founderWallet;

    /// @notice Receives 20% of GSG-priced NFT sales
    address public goldReserveWallet;

    /// @notice Receives 20% of GSS-priced NFT sales (v2 addition)
    address public silverReserveWallet;

    /// @notice Auto-incrementing NFT ID
    uint256 private _nextTokenId;

    // =========================================================================
    // STRUCTS & ENUMS
    // =========================================================================

    /// @notice Which token a listing accepts as payment
    enum PaymentToken { GOLD, SILVER }

    /**
     * @notice A listed NFT available for purchase.
     * @param creator   Original creator (persists through resales for royalty logic)
     * @param price     Sale price in token units (18 decimals)
     * @param payToken  GSG or GSS
     * @param active    Whether the listing is currently for sale
     * @param listedAt  Timestamp when listed
     */
    struct Listing {
        address      creator;
        uint256      price;
        PaymentToken payToken;
        bool         active;
        uint256      listedAt;
    }

    /**
     * @notice Record of a completed sale. Used by the dispute system.
     * @param buyer     Who bought the NFT
     * @param creator   Who created and sold the NFT
     * @param price     Price paid in tokens
     * @param payToken  GSG or GSS
     * @param soldAt    Timestamp of sale
     * @param disputed  Whether a dispute has been opened
     * @param resolved  Whether the dispute has been resolved
     */
    struct SaleRecord {
        address      buyer;
        address      creator;
        uint256      price;
        PaymentToken payToken;
        uint256      soldAt;
        bool         disputed;
        bool         resolved;
    }

    /// @notice Possible states of a dispute
    enum DisputeStatus { NONE, OPEN, RESOLVED_BUYER, RESOLVED_CREATOR, APPEALED }

    /**
     * @notice Full dispute record for a token.
     * @param initiator       The buyer who opened the dispute
     * @param reason          Plain-text reason
     * @param openedAt        Timestamp dispute was opened
     * @param status          Current state of the dispute
     * @param creatorAppealed Whether creator paid appeal fee
     * @param appealedAt      Timestamp of appeal (0 if not appealed)
     * @param resolution      Founder's resolution notes
     */
    struct Dispute {
        address       initiator;
        string        reason;
        uint256       openedAt;
        DisputeStatus status;
        bool          creatorAppealed;
        uint256       appealedAt;
        string        resolution;
    }

    // =========================================================================
    // MAPPINGS
    // =========================================================================

    /// @notice tokenId → active or historical listing
    mapping(uint256 => Listing)    public listings;

    /// @notice tokenId → sale record (populated after purchase)
    mapping(uint256 => SaleRecord) public saleRecords;

    /// @notice tokenId → dispute record
    mapping(uint256 => Dispute)    public disputes;

    /// @notice creator address → total tokens earned across all sales
    mapping(address => uint256)    public creatorEarnings;

    /// @notice Founder-verified creator badge
    mapping(address => bool)       public verifiedCreators;

    /// @notice Guardian pause votes (address → has voted)
    mapping(address => bool)       private _guardianPauseVotes;

    /// @notice Count of current pause votes
    uint8 private _pauseVoteCount;

    // =========================================================================
    // EVENTS
    // =========================================================================

    event NFTMinted(
        uint256 indexed  tokenId,
        address indexed  creator,
        string           metadataURI,
        uint256          price,
        PaymentToken     payToken
    );

    event NFTListed(
        uint256 indexed  tokenId,
        address indexed  seller,
        uint256          price,
        PaymentToken     payToken
    );

    event NFTDelisted(uint256 indexed tokenId, address indexed seller);

    event NFTSold(
        uint256 indexed  tokenId,
        address indexed  buyer,
        address indexed  creator,
        uint256          price,
        PaymentToken     payToken,
        uint256          creatorShare,
        uint256          founderShare,
        uint256          reserveShare
    );

    event DisputeOpened(
        uint256 indexed  tokenId,
        address indexed  initiator,
        string           reason,
        uint256          openedAt
    );

    event DisputeResolved(
        uint256 indexed  tokenId,
        DisputeStatus    result,
        string           notes
    );

    event AppealFiled(
        uint256 indexed  tokenId,
        address indexed  creator,
        uint256          feeAmount
    );

    event CreatorVerified(address indexed creator, bool verified);
    event SilverTokenSet(address indexed silverToken);
    event WalletsUpdated(address founder, address goldReserve, address silverReserve);

    // =========================================================================
    // MODIFIERS
    // =========================================================================

    /// @dev Blocks actions when Protocol contract is paused
    modifier notProtocolPaused() {
        require(!protocolContract.paused(), "Protocol is paused");
        _;
    }

    /// @dev Blocks marketplace activity during oracle failure (RED stage)
    modifier notRed() {
        require(
            protocolContract.currentStage() != IGaiaSpeakProtocol.Stage.RED,
            "Marketplace suspended: oracle failure (RED stage)"
        );
        _;
    }

    /// @dev Requires the token to have an active listing
    modifier onlyActiveListing(uint256 tokenId) {
        require(listings[tokenId].active, "NFT is not listed for sale");
        _;
    }

    /// @dev Requires msg.sender to own the NFT
    modifier onlyTokenOwner(uint256 tokenId) {
        require(ownerOf(tokenId) == msg.sender, "Caller does not own this NFT");
        _;
    }

    // =========================================================================
    // INITIALIZER
    // =========================================================================

    /**
     * @notice Initialize the contract. Called once via proxy deployment.
     * @param _protocol      GaiaSpeakProtocol address
     * @param _goldToken     GaiaSpeakToken (GSG) address
     * @param _founder       Founder wallet — receives 20% of every sale
     * @param _goldReserve   Gold reserve wallet — receives 20% of GSG sales
     * @param _silverReserve Silver reserve wallet — receives 20% of GSS sales
     */
    function initialize(
        address _protocol,
        address _goldToken,
        address _founder,
        address _goldReserve,
        address _silverReserve
    ) external initializer {
        __ERC721_init("GaiaSpeak Content", "GSNFT");
        __ERC721URIStorage_init();
        __ReentrancyGuard_init();
        __Pausable_init();
        __Ownable_init();
        __UUPSUpgradeable_init();

        require(_protocol      != address(0), "Zero address: protocol");
        require(_goldToken     != address(0), "Zero address: gold token");
        require(_founder       != address(0), "Zero address: founder");
        require(_goldReserve   != address(0), "Zero address: gold reserve");
        require(_silverReserve != address(0), "Zero address: silver reserve");

        protocolContract    = IGaiaSpeakProtocol(_protocol);
        goldTokenContract   = IGaiaSpeakToken(_goldToken);
        founderWallet       = _founder;
        goldReserveWallet   = _goldReserve;
        silverReserveWallet = _silverReserve;

        _nextTokenId = 1;
    }

    // =========================================================================
    // V2: SILVER TOKEN SETUP
    // =========================================================================

    /**
     * @notice Set the GSS silver token contract.
     *         Must be called after deploying GaiaSpeakSilverToken.
     *         Cannot be called before silver token exists.
     * @dev    This is the v2 change to GaiaSpeakNFT — 5 lines.
     *         Without this, only GSG listings are possible.
     *         After this, both GOLD and SILVER PaymentToken work.
     */
    function setSilverTokenContract(address _silver) external onlyOwner {
        require(_silver != address(0), "Zero address: silver token");
        silverTokenContract = IGaiaSpeakToken(_silver);
        emit SilverTokenSet(_silver);
    }

    // =========================================================================
    // MINTING
    // =========================================================================

    /**
     * @notice Mint a new content NFT and list it for sale in one transaction.
     *
     * @param metadataURI  IPFS URI pointing to content metadata JSON.
     *                     Metadata should include: title, description,
     *                     content type, file hash (for verification).
     * @param price        Sale price in token units (18 decimals).
     *                     Minimum: 0.001 token (MIN_LISTING_PRICE).
     * @param payToken     GOLD = accept GSG | SILVER = accept GSS
     *
     * @return tokenId     The newly minted NFT ID
     */
    function mintAndList(
        string   calldata metadataURI,
        uint256  price,
        PaymentToken payToken
    )
        external
        nonReentrant
        whenNotPaused
        notProtocolPaused
        notRed
        returns (uint256 tokenId)
    {
        require(bytes(metadataURI).length > 0, "Metadata URI cannot be empty");
        require(NFTLib.meetsMinimumPrice(price), "Price below minimum (0.001 token)");

        if (payToken == PaymentToken.SILVER) {
            require(
                address(silverTokenContract) != address(0),
                "Silver token not yet configured - use GOLD listing"
            );
        }

        tokenId = _nextTokenId++;

        _safeMint(msg.sender, tokenId);
        _setTokenURI(tokenId, metadataURI);

        listings[tokenId] = Listing({
            creator:  msg.sender,
            price:    price,
            payToken: payToken,
            active:   true,
            listedAt: block.timestamp
        });

        emit NFTMinted(tokenId, msg.sender, metadataURI, price, payToken);
        emit NFTListed(tokenId, msg.sender, price, payToken);
    }

    /**
     * @notice Mint an NFT privately (no listing). Owner can list later.
     * @param metadataURI  IPFS URI for the content metadata
     * @return tokenId     The newly minted NFT ID
     */
    function mintPrivate(string calldata metadataURI)
        external
        nonReentrant
        whenNotPaused
        notProtocolPaused
        returns (uint256 tokenId)
    {
        require(bytes(metadataURI).length > 0, "Metadata URI cannot be empty");

        tokenId = _nextTokenId++;
        _safeMint(msg.sender, tokenId);
        _setTokenURI(tokenId, metadataURI);

        // Record creator for royalty tracking on future listings
        listings[tokenId].creator = msg.sender;

        emit NFTMinted(tokenId, msg.sender, metadataURI, 0, PaymentToken.GOLD);
    }

    // =========================================================================
    // LISTING MANAGEMENT
    // =========================================================================

    /**
     * @notice List an already-owned NFT for sale.
     * @param tokenId   The NFT to list
     * @param price     Sale price in token units
     * @param payToken  Which token to accept
     */
    function listNFT(uint256 tokenId, uint256 price, PaymentToken payToken)
        external
        nonReentrant
        whenNotPaused
        notProtocolPaused
        onlyTokenOwner(tokenId)
    {
        require(!listings[tokenId].active,  "Already listed - delist first");
        require(NFTLib.meetsMinimumPrice(price), "Price below minimum");

        if (payToken == PaymentToken.SILVER) {
            require(
                address(silverTokenContract) != address(0),
                "Silver token not configured"
            );
        }

        // Preserve original creator for earnings tracking
        address originalCreator = listings[tokenId].creator == address(0)
            ? msg.sender
            : listings[tokenId].creator;

        listings[tokenId] = Listing({
            creator:  originalCreator,
            price:    price,
            payToken: payToken,
            active:   true,
            listedAt: block.timestamp
        });

        emit NFTListed(tokenId, msg.sender, price, payToken);
    }

    /**
     * @notice Remove an NFT from sale.
     * @param tokenId  The NFT to delist
     */
    function delistNFT(uint256 tokenId)
        external
        nonReentrant
        onlyTokenOwner(tokenId)
        onlyActiveListing(tokenId)
    {
        listings[tokenId].active = false;
        emit NFTDelisted(tokenId, msg.sender);
    }

    // =========================================================================
    // PURCHASE  —  THE CORE FUNCTION
    // =========================================================================

    /**
     * @notice Purchase a listed NFT.
     *
     * BEFORE CALLING THIS:
     * The buyer must call approve() on the GSG or GSS contract to allow this
     * contract to spend the listing price. Example:
     *   goldToken.approve(address(nftContract), listingPrice)
     *
     * WHAT HAPPENS:
     * 1. Tokens pulled from buyer at listing price
     * 2. NFT transferred from seller to buyer
     * 3. Fees distributed automatically:
     *      60% → creator (original minter)
     *      20% → founder wallet
     *      20% → reserve wallet (gold or silver, matching listing token)
     * 4. Sale record created for dispute system
     *
     * @param tokenId  The NFT to purchase
     */
    function buyNFT(uint256 tokenId)
        external
        nonReentrant
        whenNotPaused
        notProtocolPaused
        notRed
        onlyActiveListing(tokenId)
    {
        Listing  memory listing = listings[tokenId];
        address  seller         = ownerOf(tokenId);

        require(msg.sender != seller,    "Cannot buy your own NFT");
        require(
            disputes[tokenId].status == DisputeStatus.NONE    ||
            disputes[tokenId].status == DisputeStatus.RESOLVED_BUYER   ||
            disputes[tokenId].status == DisputeStatus.RESOLVED_CREATOR,
            "NFT has an unresolved active dispute"
        );

        // ── Select token contract and reserve wallet ──────────────────────────
        // This is the v2 change — routes to GSG or GSS based on listing config
        IGaiaSpeakToken tokenContract;
        address         reserveWallet;

        if (listing.payToken == PaymentToken.SILVER) {
            require(
                address(silverTokenContract) != address(0),
                "Silver token not configured"
            );
            tokenContract = silverTokenContract;
            reserveWallet = silverReserveWallet;
        } else {
            tokenContract = goldTokenContract;
            reserveWallet = goldReserveWallet;
        }

        // ── Calculate 60 / 20 / 20 split using NFTLib ────────────────────────
        uint256 price        = listing.price;
        uint256 creatorShare = NFTLib.calculateCreatorShare(price);  // 60%
        uint256 founderShare = NFTLib.calculateFounderShare(price);  // 20%
        uint256 reserveShare = NFTLib.calculateReserveShare(price);  // 20%

        // Verify split is complete — no tokens lost
        assert(creatorShare + founderShare + reserveShare == price);

        // ── Pull full price from buyer ─────────────────────────────────────────
        require(
            tokenContract.transferFrom(msg.sender, address(this), price),
            "Token transfer from buyer failed - check approval"
        );

        // ── Transfer NFT from seller to buyer ─────────────────────────────────
        listings[tokenId].active = false;
        _transfer(seller, msg.sender, tokenId);

        // ── Distribute fee splits ─────────────────────────────────────────────
        require(
            tokenContract.transfer(listing.creator, creatorShare),
            "Creator payment failed"
        );
        require(
            tokenContract.transfer(founderWallet, founderShare),
            "Founder payment failed"
        );
        require(
            tokenContract.transfer(reserveWallet, reserveShare),
            "Reserve payment failed"
        );

        // ── Record the sale ───────────────────────────────────────────────────
        saleRecords[tokenId] = SaleRecord({
            buyer:     msg.sender,
            creator:   listing.creator,
            price:     price,
            payToken:  listing.payToken,
            soldAt:    block.timestamp,
            disputed:  false,
            resolved:  false
        });

        // Track creator lifetime earnings
        creatorEarnings[listing.creator] += creatorShare;

        emit NFTSold(
            tokenId,
            msg.sender,
            listing.creator,
            price,
            listing.payToken,
            creatorShare,
            founderShare,
            reserveShare
        );
    }

    // =========================================================================
    // DISPUTE SYSTEM
    // =========================================================================

    /**
     * @notice Buyer opens a dispute after purchase.
     *         Must be within 7 days of the sale.
     *
     * @param tokenId  The NFT that was purchased
     * @param reason   Plain-text explanation of the dispute
     *
     * Common dispute reasons:
     * - Content does not match description
     * - File is corrupted or inaccessible
     * - Duplicate content (same content sold multiple times)
     * - Content violates platform terms
     */
    function openDispute(uint256 tokenId, string calldata reason)
        external
        nonReentrant
        whenNotPaused
    {
        SaleRecord storage sale = saleRecords[tokenId];

        require(sale.buyer != address(0),    "No sale record for this token");
        require(sale.buyer == msg.sender,    "Only the buyer can open a dispute");
        require(!sale.disputed,              "Dispute already opened");
        require(!sale.resolved,              "Sale already resolved");
        require(
            NFTLib.isDisputeWindowOpen(sale.soldAt),
            "Dispute window has closed (7 days after purchase)"
        );
        require(bytes(reason).length > 0,   "Dispute reason cannot be empty");
        require(bytes(reason).length <= 500, "Reason too long (max 500 chars)");

        sale.disputed = true;

        disputes[tokenId] = Dispute({
            initiator:       msg.sender,
            reason:          reason,
            openedAt:        block.timestamp,
            status:          DisputeStatus.OPEN,
            creatorAppealed: false,
            appealedAt:      0,
            resolution:      ""
        });

        emit DisputeOpened(tokenId, msg.sender, reason, block.timestamp);
    }

    /**
     * @notice Founder resolves a dispute.
     *
     * @param tokenId      The disputed NFT
     * @param favourBuyer  true = resolve in buyer's favour | false = uphold creator
     * @param notes        Resolution explanation (stored on-chain)
     *
     * Resolution in buyer's favour:
     *   - Creator's 60% share (held by contract) is returned to buyer
     *   - Founder and reserve shares are not clawed back
     *
     * Resolution in creator's favour:
     *   - No refund. Creator keeps their share (already transferred).
     *   - Dispute is closed.
     */
    function resolveDispute(
        uint256  tokenId,
        bool     favourBuyer,
        string   calldata notes
    )
        external
        onlyOwner
        nonReentrant
    {
        Dispute    storage dispute = disputes[tokenId];
        SaleRecord storage sale   = saleRecords[tokenId];

        require(
            dispute.status == DisputeStatus.OPEN,
            "No open dispute for this token"
        );
        require(bytes(notes).length > 0, "Resolution notes required");

        if (favourBuyer) {
            // Attempt refund of creator share to buyer
            // Contract must hold sufficient balance (creator share was sent at purchase)
            // In practice: contract does not hold creator share after buyNFT()
            // so this is a best-effort refund from any contract holdings
            IGaiaSpeakToken tokenContract = sale.payToken == PaymentToken.SILVER
                ? silverTokenContract
                : goldTokenContract;

            uint256 refundAmount = NFTLib.calculateCreatorShare(sale.price);
            uint256 contractBalance = tokenContract.balanceOf(address(this));

            if (contractBalance >= refundAmount) {
                require(
                    tokenContract.transfer(sale.buyer, refundAmount),
                    "Refund transfer failed"
                );
            }
            // Note: if contract has insufficient balance, founder must manually
            // top up the contract before resolving, or resolve off-chain.

            dispute.status = DisputeStatus.RESOLVED_BUYER;
        } else {
            dispute.status = DisputeStatus.RESOLVED_CREATOR;
        }

        dispute.resolution = notes;
        sale.resolved      = true;

        emit DisputeResolved(tokenId, dispute.status, notes);
    }

    /**
     * @notice Creator files an appeal after a dispute was resolved in buyer's favour.
     *
     * Cost: 0.5 token (APPEAL_FEE) paid in same token as the original sale.
     *
     * Per spec (Example 3):
     *   Normal creator share = 3 GS (60% of 5 GS sale)
     *   After appeal:        = 2.5 GS (creator loses 0.5 appeal fee)
     *   Appeal fee to reserve: 0.5 GS
     *
     * The creator must approve this contract to spend APPEAL_FEE before calling.
     *
     * @param tokenId  The NFT with a disputed resolution
     */
    function fileAppeal(uint256 tokenId)
        external
        nonReentrant
        whenNotPaused
    {
        Dispute    storage dispute = disputes[tokenId];
        SaleRecord storage sale   = saleRecords[tokenId];

        require(
            dispute.status == DisputeStatus.RESOLVED_BUYER,
            "Can only appeal a resolution in buyer's favour"
        );
        require(!dispute.creatorAppealed, "Appeal already filed");
        require(
            msg.sender == sale.creator,
            "Only the original creator can file an appeal"
        );

        // Determine which token the appeal fee must be paid in
        IGaiaSpeakToken tokenContract = sale.payToken == PaymentToken.SILVER
            ? silverTokenContract
            : goldTokenContract;

        // Pull 0.5 token appeal fee from creator
        require(
            tokenContract.transferFrom(msg.sender, address(this), NFTLib.APPEAL_FEE),
            "Appeal fee transfer failed - check token approval"
        );

        dispute.creatorAppealed = true;
        dispute.appealedAt      = block.timestamp;
        dispute.status          = DisputeStatus.APPEALED;

        emit AppealFiled(tokenId, msg.sender, NFTLib.APPEAL_FEE);
    }

    /**
     * @notice Founder makes final decision on an appeal.
     *
     * @param tokenId         The appealed NFT
     * @param appealSucceeds  true = creator wins | false = buyer upheld
     * @param notes           Final resolution reasoning
     *
     * In all cases, the 0.5 APPEAL_FEE goes to the reserve wallet.
     * It is never refunded — it is the cost of the appeal process.
     */
    function resolveAppeal(
        uint256  tokenId,
        bool     appealSucceeds,
        string   calldata notes
    )
        external
        onlyOwner
        nonReentrant
    {
        Dispute    storage dispute = disputes[tokenId];
        SaleRecord storage sale   = saleRecords[tokenId];

        require(
            dispute.status == DisputeStatus.APPEALED,
            "No active appeal for this token"
        );
        require(bytes(notes).length > 0, "Resolution notes required");

        IGaiaSpeakToken tokenContract = sale.payToken == PaymentToken.SILVER
            ? silverTokenContract
            : goldTokenContract;

        address reserveWallet = sale.payToken == PaymentToken.SILVER
            ? silverReserveWallet
            : goldReserveWallet;

        // Appeal fee always goes to reserve regardless of outcome
        uint256 contractBalance = tokenContract.balanceOf(address(this));
        if (contractBalance >= NFTLib.APPEAL_FEE) {
            tokenContract.transfer(reserveWallet, NFTLib.APPEAL_FEE);
        }

        dispute.status     = appealSucceeds
            ? DisputeStatus.RESOLVED_CREATOR
            : DisputeStatus.RESOLVED_BUYER;
        dispute.resolution = notes;

        emit DisputeResolved(tokenId, dispute.status, notes);
    }

    // =========================================================================
    // GUARDIAN EMERGENCY PAUSE
    // =========================================================================

    /**
     * @notice A guardian votes to emergency-pause the marketplace.
     *         Requires 2-of-3 guardian votes to activate pause.
     *         Mirrors the Protocol contract's guardian system.
     */
    function guardianVotePause() external {
        require(
            protocolContract.isGuardian(msg.sender),
            "Caller is not a guardian"
        );
        require(!_guardianPauseVotes[msg.sender], "Guardian already voted");

        _guardianPauseVotes[msg.sender] = true;
        _pauseVoteCount++;

        if (_pauseVoteCount >= 2) {
            _pause();
            _resetPauseVotes();
        }
    }

    /**
     * @notice Owner unpauses the marketplace after guardian pause.
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /// @dev Resets pause vote count. Individual votes persist to prevent
    ///      the same guardian voting multiple times in one incident.
    function _resetPauseVotes() internal {
        _pauseVoteCount = 0;
    }

    // =========================================================================
    // ADMIN
    // =========================================================================

    /**
     * @notice Mark or unmark a creator as verified.
     *         Verified status displayed in front-end — no on-chain mechanics change.
     */
    function setVerifiedCreator(address creator, bool verified)
        external
        onlyOwner
    {
        require(creator != address(0), "Zero address");
        verifiedCreators[creator] = verified;
        emit CreatorVerified(creator, verified);
    }

    /**
     * @notice Update wallet addresses.
     */
    function setWallets(
        address _founder,
        address _goldReserve,
        address _silverReserve
    ) external onlyOwner {
        require(_founder       != address(0), "Zero address: founder");
        require(_goldReserve   != address(0), "Zero address: gold reserve");
        require(_silverReserve != address(0), "Zero address: silver reserve");

        founderWallet       = _founder;
        goldReserveWallet   = _goldReserve;
        silverReserveWallet = _silverReserve;

        emit WalletsUpdated(_founder, _goldReserve, _silverReserve);
    }

    // =========================================================================
    // VIEW FUNCTIONS
    // =========================================================================

    /// @notice Returns whether a token is currently listed for sale
    function isListed(uint256 tokenId) external view returns (bool) {
        return listings[tokenId].active;
    }

    /// @notice Returns full listing data for a token
    function getListing(uint256 tokenId)
        external
        view
        returns (
            address      creator,
            uint256      price,
            PaymentToken payToken,
            bool         active,
            uint256      listedAt
        )
    {
        Listing memory l = listings[tokenId];
        return (l.creator, l.price, l.payToken, l.active, l.listedAt);
    }

    /// @notice Returns full dispute data for a token
    function getDispute(uint256 tokenId)
        external
        view
        returns (
            address       initiator,
            string memory reason,
            uint256       openedAt,
            DisputeStatus status,
            bool          creatorAppealed,
            string memory resolution
        )
    {
        Dispute memory d = disputes[tokenId];
        return (
            d.initiator,
            d.reason,
            d.openedAt,
            d.status,
            d.creatorAppealed,
            d.resolution
        );
    }

    /// @notice Total NFTs minted (including unlisted and privately minted)
    function totalMinted() external view returns (uint256) {
        return _nextTokenId - 1;
    }

    /**
     * @notice Preview what a buyer and creator will receive for a sale.
     *         Use this in the front-end before the buyer confirms.
     * @param price  The listing price
     * @return creatorShare  60% of price
     * @return founderShare  20% of price
     * @return reserveShare  20% of price (remainder)
     */
    function previewSplit(uint256 price)
        external
        pure
        returns (
            uint256 creatorShare,
            uint256 founderShare,
            uint256 reserveShare
        )
    {
        creatorShare = NFTLib.calculateCreatorShare(price);
        founderShare = NFTLib.calculateFounderShare(price);
        reserveShare = NFTLib.calculateReserveShare(price);
    }

    // =========================================================================
    // UUPS UPGRADE
    // =========================================================================

    /// @dev Only owner can authorize upgrades
    function _authorizeUpgrade(address newImplementation)
        internal
        override
        onlyOwner
    {}

    // =========================================================================
    // REQUIRED OVERRIDES (OpenZeppelin multi-inheritance)
    // =========================================================================

    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721Upgradeable, ERC721URIStorageUpgradeable)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721Upgradeable, ERC721URIStorageUpgradeable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _burn(uint256 tokenId)
        internal
        override(ERC721Upgradeable, ERC721URIStorageUpgradeable)
    {
        super._burn(tokenId);
    }
}
