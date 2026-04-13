// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library TokenLib {
    // Constants
    uint256 public constant MIN_PURCHASE_USD_CENTS = 100;   // $1.00
    uint256 public constant ACTION_COOLDOWN         = 60;   // seconds
    uint256 public constant REFERRALS_FOR_REWARD    = 10;
    uint256 public constant EXTERNAL_FEE_BPS        = 200;  // 2.00%
    uint256 public constant P2P_FEE_BPS             = 2;    // 0.02%
    uint256 public constant MIN_TRANSFER_TOKENS     = 5e17; // 0.5 tokens

    // Fund distribution percentages (10000 = 100%)
    uint256 public constant FOUNDER_SHARE_BPS      = 100;   // 1%
    uint256 public constant PIONEER_TOTAL_BPS      = 1;     // 0.01%
    uint256 public constant RESERVE_SHARE_BPS      = 8711;  // 87.11%
    uint256 public constant OPERATIONS_SHARE_BPS   = 1188;  // 11.88%

    // GOLD stage markup distribution
    uint256 public constant GOLD_FOUNDER_MARKUP_PCT = 40;
    uint256 public constant GOLD_RESERVE_MARKUP_PCT = 60;

    // Helper: Check if cooldown has passed
    function isCooldownExpired(uint256 lastActionTime) internal view returns (bool) {
        return block.timestamp >= lastActionTime + ACTION_COOLDOWN;
    }

    // Helper: Calculate fee amount
    function calculateFee(uint256 amount, uint256 feeBps) internal pure returns (uint256) {
        return (amount * feeBps) / 10000;
    }

    // Helper: Check if purchase meets minimum
    function meetsMinimumPurchase(uint256 sentUSD) internal pure returns (bool) {
        return sentUSD >= MIN_PURCHASE_USD_CENTS * 1e16;
    }

    // Helper: Calculate fractional gram amount
    function calculateGramAmount(uint256 sentUSD, uint256 pricePerGram) internal pure returns (uint256) {
        return (sentUSD * 1e18) / pricePerGram;
    }

    // Helper: Check if referral reward threshold reached
    function hasReferralReward(uint256 referralCount) internal pure returns (bool) {
        return referralCount % REFERRALS_FOR_REWARD == 0;
    }

    // Helper: Calculate membership duration
    function getMembershipDuration(bool annual) internal pure returns (uint256) {
        return annual ? 365 days : 30 days;
    }

    // Helper: Check if membership is valid
    function isMember(uint256 membershipExpiry) internal view returns (bool) {
        return membershipExpiry > block.timestamp;
    }
}

