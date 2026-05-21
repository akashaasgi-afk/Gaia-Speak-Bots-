// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library StageLib {
    // Pure utility functions for stage logic

    // Helper: Check if should deactivate all pioneer rewards
    function shouldDeactivateAllRewards(uint8 targetStage) internal pure returns (bool) {
        return targetStage == 3; // 3 = BLUE stage
    }
}

