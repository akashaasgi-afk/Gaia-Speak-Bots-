// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract PioneerNFT is ERC721, Ownable {
    
    // The two tokens we are wrapping
    IERC20 public GSG;
    IERC20 public GSS;

    // Mapping from NFT ID to locked amounts
    mapping(uint256 => uint256) public lockedGSGAmount;
    mapping(uint256 => uint256) public lockedGSSAmount;

    uint256 public nextTokenId = 1;

    constructor(address _GSG, address _GSS) ERC721("GaiaSpeak Pioneer", "PIONEER") {
        GSG = IERC20(_GSG);
        GSS = IERC20(_GSS);
    }

    /**
     * @notice Wrap GSG and GSS tokens into a permanent Pioneer NFT
     * @param gsgAmount Amount of GSG to lock
     * @param gssAmount Amount of GSS to lock
     */
    function wrapTokens(uint256 gsgAmount, uint256 gssAmount) external {
        require(gsgAmount > 0 || gssAmount > 0, "Must wrap at least one token");

        // Transfer tokens from user to this contract (lock them)
        if (gsgAmount > 0) {
            GSG.transferFrom(msg.sender, address(this), gsgAmount);
        }
        if (gssAmount > 0) {
            GSS.transferFrom(msg.sender, address(this), gssAmount);
        }

        // Mint Pioneer NFT to the user
        uint256 tokenId = nextTokenId++;
        _safeMint(msg.sender, tokenId);

        // Record locked amounts
        lockedGSGAmount[tokenId] = gsgAmount;
        lockedGSSAmount[tokenId] = gssAmount;
    }

    /**
     * @notice View locked amounts for a specific Pioneer NFT
     */
    function getLockedAmounts(uint256 tokenId) external view returns (uint256 gsg, uint256 gss) {
        return (lockedGSGAmount[tokenId], lockedGSSAmount[tokenId]);
    }

}