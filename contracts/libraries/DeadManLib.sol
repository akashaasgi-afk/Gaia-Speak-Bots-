// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library DeadManLib {
    uint256 public constant HEARTBEAT_INTERVAL = 30 days;

    // Helper: Check if heartbeat is expired
    function isHeartbeatExpired(uint256 lastHeartbeat) internal view returns (bool) {
        return block.timestamp > lastHeartbeat + HEARTBEAT_INTERVAL;
    }

    // Helper: Compute death proof ID
    function getProofId(uint8 proofType, bytes32 proofHash) internal pure returns (bytes32) {
        return keccak256(abi.encode(proofType, proofHash));
    }

    // Helper: Check if all 3 proofs have been submitted
    function allProofsSubmitted(
        bytes32 familyProofId,
        bytes32 companyProofId,
        bytes32 thirdPartyProofId,
        mapping(bytes32 => bool) storage deathProofSubmitted
    ) internal view returns (bool) {
        return familyProofId != bytes32(0) &&
               companyProofId != bytes32(0) &&
               thirdPartyProofId != bytes32(0) &&
               deathProofSubmitted[familyProofId] &&
               deathProofSubmitted[companyProofId] &&
               deathProofSubmitted[thirdPartyProofId];
    }
}

