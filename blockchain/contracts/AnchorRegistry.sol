// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Demo contract: stores one Merkle root per epoch on a local Hardhat chain.
/// This local chain demonstrates external anchoring; it is not a production public chain.
contract AnchorRegistry {
    mapping(uint256 => bytes32) public roots;
    mapping(uint256 => bool) public anchored;

    event RootAnchored(uint256 indexed epochId, bytes32 root, address indexed submitter);

    function submitRoot(uint256 epochId, bytes32 root) external {
        require(!anchored[epochId], "Epoch already anchored");
        require(root != bytes32(0), "Root cannot be zero");
        roots[epochId] = root;
        anchored[epochId] = true;
        emit RootAnchored(epochId, root, msg.sender);
    }
}
