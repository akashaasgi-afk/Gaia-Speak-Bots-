// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface AggregatorV3Interface {
    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
}

interface IGoldOracle {
    function getGoldPriceUSD() external view returns (uint256);
}

library OracleLib {
    uint256 public constant CHAINLINK_STALENESS      = 3600;  // 1 hour
    uint256 public constant ORACLE_CONSENSUS_REQUIRED = 3;    // 3 of 5 must agree
    uint256 public constant ORACLE_TOLERANCE_PERCENT  = 2;    // within 2%
    uint256 public constant TROY_OZ_PER_GRAM = 31103476; // 31.103476 × 1e6

    // Gold price — 5-oracle median consensus
    function getGoldPriceUSD(
        address[5] memory oracleAddresses
    ) internal view returns (uint256) {
        uint256[5] memory prices;
        uint8 valid = 0;

        for (uint i = 0; i < 5; i++) {
            try IGoldOracle(oracleAddresses[i]).getGoldPriceUSD()
                returns (uint256 p) {
                if (p > 0) {
                    prices[valid] = p;
                    valid++;
                }
            } catch {}
        }

        require(valid >= ORACLE_CONSENSUS_REQUIRED, "Insufficient oracle responses");

        uint256 median = _getMedian(prices, valid);

        // Check consensus — valid sources must be within 2% of median
        uint8 agreements = 0;
        for (uint i = 0; i < valid; i++) {
            uint256 diff = prices[i] > median
                ? prices[i] - median
                : median - prices[i];
            uint256 pct = (diff * 100) / median;
            if (pct <= ORACLE_TOLERANCE_PERCENT) agreements++;
        }

        require(agreements >= ORACLE_CONSENSUS_REQUIRED, "Oracle consensus failed");

        // Convert troy oz price to per-gram price
        return (median * 1e6) / TROY_OZ_PER_GRAM;
    }

    // Silver price — Chainlink XAG/USD
    function getSilverPriceUSD(
        AggregatorV3Interface silverUsdFeed
    ) internal view returns (uint256) {
        (, int256 price, , uint256 updatedAt,) = silverUsdFeed.latestRoundData();
        require(price > 0, "Invalid silver price");
        require(
            block.timestamp - updatedAt <= CHAINLINK_STALENESS,
            "Silver oracle stale"
        );
        // Chainlink silver is USD per troy oz, 8 decimals
        // Convert to per-gram, scale to 18 decimals
        uint256 pricePerOz = uint256(price) * 1e10; // → 18 decimals
        return (pricePerOz * 1e6) / TROY_OZ_PER_GRAM;
    }

    // Median calculation
    function _getMedian(uint256[5] memory arr, uint8 count)
        internal pure returns (uint256)
    {
        // Bubble sort (small array, gas acceptable)
        for (uint i = 0; i < count - 1; i++) {
            for (uint j = 0; j < count - i - 1; j++) {
                if (arr[j] > arr[j+1]) {
                    (arr[j], arr[j+1]) = (arr[j+1], arr[j]);
                }
            }
        }
        return arr[count / 2];
    }

    // Oracle health check
    function getOracleHealth(
        AggregatorV3Interface ethUsdFeed,
        address[5] memory oracleAddresses
    ) internal view returns (
        bool chainlinkHealthy,
        uint256 responsiveOracles,
        bool systemHealthy
    ) {
        // Check Chainlink ETH/USD staleness
        try ethUsdFeed.latestRoundData() returns (
            uint80, int256 price, uint256, uint256 updatedAt, uint80
        ) {
            chainlinkHealthy = (
                price > 0 &&
                block.timestamp - updatedAt <= CHAINLINK_STALENESS
            );
        } catch {
            chainlinkHealthy = false;
        }

        // Count responsive gold oracles
        responsiveOracles = 0;
        for (uint256 i = 0; i < 5; i++) {
            try IGoldOracle(oracleAddresses[i]).getGoldPriceUSD()
                returns (uint256 p) {
                if (p > 0) responsiveOracles++;
            } catch {}
        }

        systemHealthy = chainlinkHealthy &&
            responsiveOracles >= ORACLE_CONSENSUS_REQUIRED;
    }
}

