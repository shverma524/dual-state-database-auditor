const hre = require("hardhat");

async function main() {
  const Factory = await hre.ethers.getContractFactory("AnchorRegistry");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();
  console.log("CONTRACT_ADDRESS=" + await contract.getAddress());
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
