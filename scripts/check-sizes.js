import fs from 'fs';
import path from 'path';

function getContractSize(contractName, fileName) {
    try {
        const artifactPath = `artifacts/contracts/${fileName}.sol/${contractName}.json`;
        const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
        const bytecode = artifact.bytecode;
        const deployedBytecode = artifact.deployedBytecode;

        // Remove 0x prefix and calculate size in bytes
        const bytecodeSize = (bytecode.length - 2) / 2;
        const deployedBytecodeSize = (deployedBytecode.length - 2) / 2;

        return {
            name: contractName,
            bytecodeSize,
            deployedBytecodeSize
        };
    } catch (error) {
        return {
            name: contractName,
            error: error.message
        };
    }
}

const contracts = [
    { name: 'GaiaSpeakToken', file: 'GaiaspeakToken' },  // note file vs contract name
    { name: 'GaiaSpeakSilverToken', file: 'GaiaSpeakSilverToken' },
    { name: 'GaiaSpeakNFT', file: 'GaiaSpeakNFT' },
    { name: 'GaiaSpeakProtocol', file: 'GaiaSpeakProtocol' }
];

console.log('Contract Bytecode Sizes:');
console.log('========================');

contracts.forEach(contract => {
    const size = getContractSize(contract.name, contract.file);
    if (size.error) {
        console.log(`${size.name}: Error - ${size.error}`);
    } else {
        const deployedKB = (size.deployedBytecodeSize / 1024).toFixed(2);
        const bytecodeKB = (size.bytecodeSize / 1024).toFixed(2);

        console.log(`${size.name}:`);
        console.log(`  Bytecode: ${bytecodeKB} KB (${size.bytecodeSize} bytes)`);
        console.log(`  Deployed: ${deployedKB} KB (${size.deployedBytecodeSize} bytes)`);

        // Check if deployed bytecode exceeds 24KB limit
        if (size.deployedBytecodeSize > 24576) {
            console.log(`  ⚠️  EXCEEDS 24KB LIMIT by ${((size.deployedBytecodeSize - 24576) / 1024).toFixed(2)} KB`);
        } else {
            console.log(`  ✅ Within 24KB limit`);
        }
        console.log();
    }
});
