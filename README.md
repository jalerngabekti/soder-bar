# soder-bar: Cross-Chain Bridge Event Listener Simulation

This repository contains a Python-based simulation of a crucial off-chain component for a cross-chain bridge: the **Event Listener**. This script is designed to be architecturally robust, demonstrating how to reliably listen for on-chain events on a source chain, handle real-world issues like blockchain reorganizations and RPC failures, and trigger corresponding actions on a destination chain.

## Concept

In a typical lock-and-mint or burn-and-release cross-chain bridge, assets are locked or burned in a smart contract on the source chain. This action emits an event (e.g., `TokensDeposited`). An off-chain network of listeners, often called validators or relayers, must securely observe these events.

Once an event is observed and confirmed, the listener submits a signed message or transaction to a smart contract on the destination chain, authorizing it to mint a corresponding wrapped asset or release a native asset to the user.

This script simulates the 'observe and relay' part of this process. It connects to a source chain (e.g., Ethereum Sepolia testnet), listens for specific events from a designated bridge contract, and makes a simulated API call to an 'oracle' service that would be responsible for executing the transaction on the destination chain.

## Code Architecture

The script is built with a clear separation of concerns, using several classes to manage different responsibilities:

```
[ Source Chain (RPC Node) ]
          ^
          | (HTTP/S)
          v
+---------------------------+
|  BlockchainNodeConnector  |  (Manages RPC connection, retries, data fetching)
+---------------------------+
          ^
          | (Web3.py instance)
          v
+---------------------------+
|      script.py (Main)     |
|                           |
|  +---------------------+  |  +--------------------------+
|  | BridgeContractHandler |  |  DestinationChainOracle  |
|  | (Parses event logs)   |  |  (Submits mint requests) |
|  +---------------------+  |  +--------------------------+
|            ^
|            | (Core Logic)
|            v
|  +------------------------+
|  | CrossChainEventHandler | (Main loop, state management, reorg handling)
|  +------------------------+
+---------------------------+
          ^
          | (HTTP POST)
          v
[ Oracle / Destination Chain Service ]
```

-   **`BlockchainNodeConnector`**: A resilient wrapper for connecting to an Ethereum-like RPC node. It handles initial connection failures with exponential backoff and provides clean methods for fetching blocks, headers, and event logs.

-   **`BridgeContractHandler`**: Responsible for contract-specific logic. It holds the contract's ABI and address, and its primary function is to parse raw event logs into structured, human-readable data.

-   **`DestinationChainOracle`**: Simulates the component that would submit a transaction to the destination chain. In this simulation, it makes a POST request to a mock API endpoint, representing the handoff of the processed event data.

-   **`CrossChainEventHandler`**: The orchestrator. It contains the main application loop. It uses the other components to manage state (saving the last processed block to a file), detect and handle blockchain reorganizations, fetch and process events in batches, and call the oracle.

## How it Works

1.  **Initialization**: The script starts, loads configuration from a `.env` file (RPC URL, contract address), and initializes the main `CrossChainEventHandler`.
2.  **State Loading**: It checks for a `last_processed_block.json` file. If found, it resumes scanning from where it left off. Otherwise, it starts from a configured `START_BLOCK`.
3.  **Main Loop**: The script enters an infinite loop to continuously poll the blockchain.
4.  **Block Syncing**: It fetches the latest block number from the source chain and compares it to its last processed block. It waits for a certain number of `CONFIRMATION_BLOCKS` to pass to avoid processing unconfirmed blocks.
5.  **Reorg Detection**: Before processing a new batch of blocks, it fetches the header of the *next* block (`last_processed_block + 1`). It compares its `parentHash` with the known hash of the `last_processed_block`. If they don't match, a reorganization is detected. The script then rolls back a safe number of blocks and resumes scanning from there.
6.  **Event Fetching**: It queries the RPC node for event logs within a specific block range and for the target contract address.
7.  **Event Processing**: If logs are found, the `BridgeContractHandler` parses them. For each valid 'deposit' event, the `DestinationChainOracle` is called to simulate a mint request.
8.  **State Persistence**: After successfully processing a batch of blocks, it updates its internal state (`last_processed_block` and `last_processed_block_hash`) and saves it to the `last_processed_block.json` file.
9.  **Error Handling**: The entire loop is wrapped in error handling to gracefully manage RPC node downtime or other transient errors, with appropriate sleep/retry intervals.

## Usage Example

This simulation is configured to run against the Ethereum Sepolia testnet.

### 1. Prerequisites

-   Python 3.8+
-   An RPC endpoint URL for the Sepolia testnet (e.g., from [Infura](https://infura.io), [Alchemy](https://www.alchemy.com), etc.).

### 2. Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url> soder-bar
    cd soder-bar
    ```

2.  **Create a Python virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a configuration file:**
    Create a file named `.env` in the root of the project and add your configuration details. The script will listen to `Transfer` events from the official Sepolia WETH contract as an example.

    ```dotenv
    # .env file
    RPC_URL="https://sepolia.infura.io/v3/YOUR_PROJECT_ID"
    CONTRACT_ADDRESS="0x7b79995e5f793A07Bc00c21412e50Ea00A78982e" # WETH on Sepolia
    START_BLOCK="5500000" # A recent block number to start scanning from
    ```

### 3. Run the Script

Execute the main script from your terminal:

```bash
python script.py
```

### Expected Output

You will see log messages indicating the script's progress. It will connect to the node, load its state, and begin scanning blocks. When it finds a `Transfer` event on the WETH contract, it will log the parsed event and the simulated submission to the oracle.

```
2023-10-27 14:30:01 - INFO - [CrossChainListener] - Successfully connected to RPC node at https://sepolia.infura.io/v3/...
2023-10-27 14:30:02 - INFO - [CrossChainListener] - Loaded state from last_processed_block.json: {'last_processed_block': 5500100, ...}
2023-10-27 14:30:02 - INFO - [CrossChainListener] - Starting cross-chain event listener for contract 0x7b79995e5f793A07Bc00c21412e50Ea00A78982e.
...
2023-10-27 14:30:15 - INFO - [CrossChainListener] - Scanning blocks from 5500101 to 5500200...
2023-10-27 14:30:18 - INFO - [CrossChainListener] - Found 3 potential deposit events in block range.
2023-10-27 14:30:18 - INFO - [CrossChainListener] - Parsed deposit event found in block 5500152: 10000000000000000 tokens from 0x... to 0x...
2023-10-27 14:30:18 - INFO - [CrossChainListener] - Submitting mint request to oracle: {'sourceTransactionHash': '0x...', ...}
2023-10-27 14:30:19 - INFO - [CrossChainListener] - Successfully submitted mint request for 0x.... Response: {...}
...
```
