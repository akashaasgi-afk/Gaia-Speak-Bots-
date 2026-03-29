// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GoldSupplyChain {
    string public constant ASSET_TYPE = "GOLD";
    string public constant TOKEN_NAME = "Gold Asset Token";
    string public constant SYMBOL = "GOLD";

    address public owner;
    mapping(address => bool) public isWhitelisted;

    // Har wallet ka balance track karne ke liye
    mapping(address => uint256) public balances;

    event AssetTracked(string action, uint256 timestamp);
    event WhitelistUpdated(address indexed account, bool status);
    event Transfer(address indexed from, address indexed to, uint256 value);

    constructor() {
        owner = msg.sender;
        isWhitelisted[msg.sender] = true;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this");
        _;
    }

    // Tokens paida karke wallets mein bhejne ke liye function
    function mint(address _to, uint256 _amount) public onlyOwner {
        balances[_to] += _amount;
        emit Transfer(address(0), _to, _amount);
        emit AssetTracked("Tokens Minted for Test", block.timestamp);
    }

    function addToWhitelist(address _account) public onlyOwner {
        isWhitelisted[_account] = true;
        emit WhitelistUpdated(_account, true);
    }
}