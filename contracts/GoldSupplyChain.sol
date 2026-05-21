// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract GoldSupplyChain is ERC20, Ownable {
    // --- STATE VARIABLES ---
    string public constant ASSET_TYPE = "GOLD";

    address public operationsWallet;
    address public pioneerWallet;
    address public reserveWallet; // Naya Reserve Wallet variable

    // Bogdan ki naye instructions ke mutabiq dynamic percentages
    uint256 public operationsPercent = 9899; // Default: 98.99%
    uint256 public reservePercent = 0;        // Default: 0% (Abhi disabled hai)
    uint256 public founderPercent = 100;     // 1.00%
    uint256 public pioneerPercent = 1;       // 0.01%

    bool public greenStageActive = true; 
    mapping(address => bool) public isWhitelisted;

    // --- GOLD TRACKING ---
    struct GoldBatch {
        uint256 id;
        string origin;
        uint256 weight;
    }
    mapping(uint256 => GoldBatch) public goldInventory;

    // --- EVENTS ---
    event SyncWithFrontend(string message, uint256 amount);
    event FundsDistributed(uint256 ops, uint256 res, uint256 founder, uint256 pioneer);
    event ReserveAllocationUpdated(uint256 newReserve, uint256 newOps);
    event GreenStageDeactivated();

    constructor(address _initialOwner) ERC20("Gaiaspeak Gold", "GSG") Ownable() {
        _transferOwnership(_initialOwner);

        operationsWallet = _initialOwner;
        pioneerWallet = _initialOwner;
        reserveWallet = _initialOwner; // Default founder par set kiya hai
        isWhitelisted[_initialOwner] = true;
    }

    // --- NEW FUNCTIONS (As per Bogdan's Instructions) ---

    /**
     * @dev Change 2: Founder can dynamically shift funds from Operations to Reserve.
     */
    function setReserveAllocation(uint256 _newReservePercent) external onlyOwner {
        require(_newReservePercent <= 9899, "Cannot exceed operations allocation");
        reservePercent = _newReservePercent;
        operationsPercent = 9899 - _newReservePercent;
        emit ReserveAllocationUpdated(_newReservePercent, operationsPercent);
    }

    /**
     * @dev Change 3: Manual switch to stop Pioneer rewards after GREEN stage.
     */
    function deactivateGreenStage() external onlyOwner {
        greenStageActive = false;
        emit GreenStageDeactivated();
    }

    // --- MANAGEMENT FUNCTIONS ---

    function setWallets(address _ops, address _pioneer, address _reserve) external onlyOwner {
        operationsWallet = _ops;
        pioneerWallet = _pioneer;
        reserveWallet = _reserve;
    }

    function withdraw() external onlyOwner {
        (bool success, ) = payable(owner()).call{value: address(this).balance}("");
        require(success, "Withdraw failed");
    }

    function addToWhitelist(address _account) public onlyOwner {
        isWhitelisted[_account] = true;
    }

    // --- MINTING ---
    function mint(address _to, uint256 _amount) public onlyOwner {
        require(isWhitelisted[_to], "Not Whitelisted");
        _mint(_to, _amount); 
        emit SyncWithFrontend("Tokens Minted via Professional Standard", _amount);
    }

    // --- UPDATED DISTRIBUTION LOGIC (Change 1) ---
    receive() external payable {
        uint256 amount = msg.value;
        require(amount > 0, "No MATIC sent");

        // Dynamic calculation based on setReserveAllocation
        uint256 opsAmt = (amount * operationsPercent) / 10000;
        uint256 resAmt = (amount * reservePercent) / 10000;
        uint256 founderAmt = (amount * founderPercent) / 10000;

        // Secure Transfers
        if (opsAmt > 0) payable(operationsWallet).transfer(opsAmt);
        if (resAmt > 0) payable(reserveWallet).transfer(resAmt);
        payable(owner()).transfer(founderAmt);

        // Pioneer rewards only active in GREEN stage
        uint256 pioneerAmt = 0;
        if (greenStageActive) {
            pioneerAmt = (amount * pioneerPercent) / 10000;
            payable(pioneerWallet).transfer(pioneerAmt);
        }

        emit FundsDistributed(opsAmt, resAmt, founderAmt, pioneerAmt);
    }

    // --- GOLD TRACKING FUNCTION ---
    function registerGoldBatch(uint256 _id, string memory _origin, uint256 _weight) public onlyOwner {
        goldInventory[_id] = GoldBatch(_id, _origin, _weight);
    }

    /**
     * @dev Token Identity (Logo and Branding)
     */
    function tokenURI(uint256) public view returns (string memory) {
        return "ipfs://bafkreih3pzzxj54ko4ha4tfwghcfozsdfn7oiuytfihj53ocsjmdurqazi";
    }

    /**
     * @dev Batch update for suppliers.
     */
    function updateSuppliersList(address[] memory _newAddresses) external onlyOwner {
        for (uint i = 0; i < _newAddresses.length; i++) {
            require(_newAddresses[i] != address(0), "Invalid address detected");
            isWhitelisted[_newAddresses[i]] = true;
        }
    }
}