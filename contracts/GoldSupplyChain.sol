// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@chainlink/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";

contract GoldSupplyChain {
    AggregatorV3Interface internal goldPriceFeed;
    address public owner;

    constructor() {
        owner = msg.sender;
        // Is address ko huba-hoo copy karein
        goldPriceFeed = AggregatorV3Interface(0x214ed9Da11d2F37ae002Ac44d148bcA4500366d4);
    }

    function getLatestGoldPrice() public view returns (int) {
        ( , int price, , , ) = goldPriceFeed.latestRoundData();
        return price;
    }
}