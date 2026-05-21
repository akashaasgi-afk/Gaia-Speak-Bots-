// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library GuardianLib {
    // Helper: Check pause approval threshold
    function isPauseApprovalThresholdMet(uint8 approvalCount) internal pure returns (bool) {
        return approvalCount >= 2;
    }
}

