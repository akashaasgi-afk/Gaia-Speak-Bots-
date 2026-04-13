// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library NFTLib {
    // Constants for fee distribution
    uint256 public constant CREATOR_SHARE_BPS   = 6000;   // 60%
    uint256 public constant FOUNDER_SHARE_BPS   = 2000;   // 20%
    uint256 public constant RESERVE_SHARE_BPS   = 2000;   // 20%
    uint256 public constant BPS_DENOMINATOR     = 10000;

    // Appeal and dispute constants
    uint256 public constant APPEAL_FEE          = 5e17;   // 0.5 token
    uint256 public constant DISPUTE_WINDOW      = 7 days;
    uint256 public constant MIN_LISTING_PRICE   = 1e15;   // 0.001 token

    // Dispute resolution outcomes
    enum DisputeOutcome { PENDING, BUYER_WINS, CREATOR_WINS, REFUND_FULL }

    // Helper: Calculate creator share from sale price
    function calculateCreatorShare(uint256 price) internal pure returns (uint256) {
        return (price * CREATOR_SHARE_BPS) / BPS_DENOMINATOR;
    }

    // Helper: Calculate founder share from sale price
    function calculateFounderShare(uint256 price) internal pure returns (uint256) {
        return (price * FOUNDER_SHARE_BPS) / BPS_DENOMINATOR;
    }

    // Helper: Calculate reserve share from sale price
    function calculateReserveShare(uint256 price) internal pure returns (uint256) {
        return (price * RESERVE_SHARE_BPS) / BPS_DENOMINATOR;
    }

    // Helper: Check if dispute window is still open
    function isDisputeWindowOpen(uint256 soldAt) internal view returns (bool) {
        return block.timestamp <= soldAt + DISPUTE_WINDOW;
    }

    // Helper: Check if appeal fee is sufficient
    function isAppealFeeSufficient(uint256 amount) internal pure returns (bool) {
        return amount >= APPEAL_FEE;
    }

    // Helper: Check if listing price meets minimum
    function meetsMinimumPrice(uint256 price) internal pure returns (bool) {
        return price >= MIN_LISTING_PRICE;
    }

    // Helper: Distribute sales proceeds
    function distributeSaleProceeds(
        uint256 price,
        address creator,
        address founderWallet,
        address reserveWallet,
        function(address, uint256) internal transfer
    ) internal {
        uint256 creatorShare = calculateCreatorShare(price);
        uint256 founderShare = calculateFounderShare(price);
        uint256 reserveShare = calculateReserveShare(price);

        transfer(creator, creatorShare);
        transfer(founderWallet, founderShare);
        transfer(reserveWallet, reserveShare);
    }
}

