import os
import time
import json
import logging
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound, MismatchedABI
from requests.exceptions import ConnectionError as RequestsConnectionError

# --- Configuration --- #

# Load environment variables from .env file
load_dotenv()

# Set up a structured logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('CrossChainListener')

# --- Constants --- #

# The number of blocks to wait for confirmation to reduce risks of chain reorgs.
CONFIRMATION_BLOCKS = 6

# Polling interval in seconds when no new blocks are found.
POLL_INTERVAL_SECONDS = 10

# Retry interval for RPC connection errors, with exponential backoff.
RPC_RETRY_BASE_SECONDS = 5
RPC_RETRY_MAX_ATTEMPTS = 5

# File to persist the last processed block number.
STATE_FILE = 'last_processed_block.json'

class BlockchainNodeConnector:
    """
    Manages the connection to a blockchain node via RPC.
    This class acts as a resilient wrapper around the Web3.py library,
    handling connection errors and retries.
    """

    def __init__(self, rpc_url: str):
        """
        Initializes the connector and establishes a connection to the node.

        Args:
            rpc_url (str): The HTTP RPC endpoint of the blockchain node.
        """
        self.rpc_url = rpc_url
        self.web3 = None
        self._connect()

    def _connect(self):
        """
        Establishes a connection to the RPC endpoint with retry logic.
        """
        attempts = 0
        while attempts < RPC_RETRY_MAX_ATTEMPTS:
            try:
                self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if self.web3.is_connected():
                    logger.info(f"Successfully connected to RPC node at {self.rpc_url}")
                    return
                else:
                    raise RequestsConnectionError("Web3 provider reports not connected.")
            except RequestsConnectionError as e:
                attempts += 1
                wait_time = RPC_RETRY_BASE_SECONDS * (2 ** (attempts - 1))
                logger.error(f"RPC connection failed (Attempt {attempts}/{RPC_RETRY_MAX_ATTEMPTS}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        logger.critical("Failed to connect to RPC node after multiple retries. Exiting.")
        raise ConnectionError("Could not establish connection to the blockchain node.")

    def get_latest_block_number(self) -> int:
        """
        Fetches the most recent block number from the blockchain.

        Returns:
            int: The latest block number.
        """
        try:
            return self.web3.eth.block_number
        except Exception as e:
            logger.error(f"Failed to get latest block number: {e}")
            self._connect() # Attempt to reconnect
            return self.web3.eth.block_number

    def get_block_header(self, block_identifier: Any) -> Optional[Dict[str, Any]]:
        """
        Retrieves the header for a specific block.
        Used for reorg detection by comparing block hashes.

        Args:
            block_identifier (Any): The block number or hash.

        Returns:
            Optional[Dict[str, Any]]: The block header as a dictionary, or None on failure.
        """
        try:
            block = self.web3.eth.get_block(block_identifier, full_transactions=False)
            return block
        except BlockNotFound:
            logger.warning(f"Block {block_identifier} not found.")
            return None
        except Exception as e:
            logger.error(f"Error fetching block header for {block_identifier}: {e}")
            return None

    def get_logs(self, from_block: int, to_block: int, address: str, topics: list) -> list:
        """
        Fetches event logs within a specified block range.

        Args:
            from_block (int): The starting block number.
            to_block (int): The ending block number.
            address (str): The contract address to filter by.
            topics (list): A list of event topics to filter by.

        Returns:
            list: A list of event log entries.
        """
        try:
            return self.web3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': address,
                'topics': topics
            })
        except Exception as e:
            logger.error(f"Error fetching logs from block {from_block} to {to_block}: {e}")
            return []

class BridgeContractHandler:
    """
    Handles interactions with the bridge smart contract, specifically event parsing.
    """

    def __init__(self, web3_instance: Web3, contract_address: str, contract_abi: list):
        """
        Initializes the contract handler.

        Args:
            web3_instance (Web3): An active Web3 instance.
            contract_address (str): The address of the bridge smart contract.
            contract_abi (list): The ABI of the smart contract.
        """
        self.web3 = web3_instance
        self.contract_address = contract_address
        self.contract = self.web3.eth.contract(address=contract_address, abi=contract_abi)

    def parse_deposit_event(self, log: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parses a raw log entry into a structured 'TokensDeposited' event.
        In this simulation, we use the standard 'Transfer' event as a proxy.

        Args:
            log (Dict[str, Any]): The raw log entry from `get_logs`.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with parsed event data or None if parsing fails.
        """
        try:
            # The `events` object on the contract instance can process logs.
            event_data = self.contract.events.Transfer().process_log(log)
            return {
                'transactionHash': event_data['transactionHash'].hex(),
                'blockNumber': event_data['blockNumber'],
                'from': event_data['args']['from'],
                'to': event_data['args']['to'], # In a real bridge, this might be the bridge contract itself
                'amount': event_data['args']['value'],
                'logIndex': event_data['logIndex']
            }
        except MismatchedABI:
            logger.error(f"Log parsing failed due to ABI mismatch for tx {log['transactionHash'].hex()}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during log parsing: {e}")
            return None


class DestinationChainOracle:
    """
    Simulates the component responsible for submitting transactions to the destination chain.
    In a real-world scenario, this would be a secure service that holds private keys,
    manages nonces, and pays for gas.
    """

    def __init__(self, api_endpoint: str):
        """
        Initializes the oracle simulator.

        Args:
            api_endpoint (str): A mock API endpoint to post mint requests to.
        """
        self.api_endpoint = api_endpoint

    def submit_mint_request(self, deposit_tx_hash: str, recipient: str, amount: int) -> bool:
        """
        Simulates submitting a request to mint tokens on the destination chain.

        Args:
            deposit_tx_hash (str): The hash of the source chain deposit transaction for idempotency.
            recipient (str): The address to receive tokens on the destination chain.
            amount (int): The amount of tokens to mint (in wei).

        Returns:
            bool: True if the request was successfully submitted, False otherwise.
        """
        payload = {
            'sourceTransactionHash': deposit_tx_hash,
            'recipient': recipient,
            'amount': str(amount), # Use string for large numbers
            'destinationChainId': 421614 # Example: Arbitrum Sepolia
        }
        try:
            # In a real system, this would be a signed request to a secure backend.
            logger.info(f"Submitting mint request to oracle: {payload}")
            response = requests.post(self.api_endpoint, json=payload, timeout=10)
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Successfully submitted mint request for {deposit_tx_hash}. Response: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to submit mint request for {deposit_tx_hash} to oracle service: {e}")
            return False


class CrossChainEventHandler:
    """
    The core component of the listener. It orchestrates the process of fetching blocks,
    parsing events, handling state, and triggering actions on the destination chain.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the event handler with all its dependencies.

        Args:
            config (Dict[str, Any]): A dictionary containing configuration parameters.
        """
        self.config = config
        self.connector = BlockchainNodeConnector(config['rpc_url'])
        self.contract_handler = BridgeContractHandler(
            self.connector.web3,
            config['contract_address'],
            config['contract_abi']
        )
        self.oracle = DestinationChainOracle(config['oracle_api_endpoint'])
        self.state = self._load_state()
        self.last_processed_block = self.state.get('last_processed_block', config['start_block'])
        self.last_processed_block_hash = self.state.get('last_processed_block_hash', None)

    def _load_state(self) -> Dict[str, Any]:
        """
        Loads the last processed block number from a state file to allow resumption.
        """
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Loaded state from {STATE_FILE}: {state}")
                    return state
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Could not read state file {STATE_FILE}: {e}. Starting from scratch.")
        return {}

    def _save_state(self):
        """
        Saves the current state (last processed block number and hash) to the state file.
        """
        state = {
            'last_processed_block': self.last_processed_block,
            'last_processed_block_hash': self.last_processed_block_hash
        }
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f)
        except IOError as e:
            logger.error(f"Could not write to state file {STATE_FILE}: {e}")

    def _handle_reorg(self, current_block_number: int) -> int:
        """
        Detects and handles a blockchain reorganization.
        If a reorg is detected, it steps back a few blocks to ensure consistency.
        
        Returns:
            int: The new, safe block number to start processing from.
        """
        logger.warning("Potential blockchain reorganization detected!")
        logger.info(f"Rolling back {CONFIRMATION_BLOCKS} blocks to handle reorg.")
        safe_block = max(self.config['start_block'], current_block_number - CONFIRMATION_BLOCKS * 2)
        self.last_processed_block = safe_block
        self.last_processed_block_hash = None # Reset hash to force re-fetch
        self._save_state()
        logger.info(f"Resuming scan from block {safe_block}")
        return safe_block

    def process_block_range(self, from_block: int, to_block: int):
        """
        Processes a range of blocks, fetches logs, and triggers oracle actions.
        """
        logger.info(f"Scanning blocks from {from_block} to {to_block}...")
        deposit_event_topic = self.connector.web3.keccak(text="Transfer(address,address,uint256)").hex()
        
        logs = self.connector.get_logs(
            from_block=from_block,
            to_block=to_block,
            address=self.config['contract_address'],
            topics=[deposit_event_topic]
        )

        if not logs:
            return

        logger.info(f"Found {len(logs)} potential deposit events in block range.")

        for log in sorted(logs, key=lambda x: (x['blockNumber'], x['logIndex'])):
            parsed_event = self.contract_handler.parse_deposit_event(log)
            if parsed_event:
                logger.info(f"Parsed deposit event found in block {parsed_event['blockNumber']}: "
                            f"{parsed_event['amount']} tokens from {parsed_event['from']} to {parsed_event['to']}")
                
                # For this simulation, we assume the 'from' address is the final recipient on the other chain.
                success = self.oracle.submit_mint_request(
                    deposit_tx_hash=parsed_event['transactionHash'],
                    recipient=parsed_event['from'],
                    amount=parsed_event['amount']
                )
                if not success:
                    # In a real system, this would trigger a robust retry/alerting mechanism.
                    logger.error(f"Oracle submission failed for {parsed_event['transactionHash']}. This event will be retried on next run.")
                    # We stop processing here to ensure events are handled in order.
                    # The last_processed_block is not updated, so we will retry from here.
                    return

    def run(self):
        """
        The main execution loop for the event listener.
        """
        logger.info(f"Starting cross-chain event listener for contract {self.config['contract_address']}.")
        logger.info(f"Initial starting block is {self.last_processed_block}.")

        while True:
            try:
                latest_on_chain = self.connector.get_latest_block_number()
                
                # The target block up to which we can safely scan
                target_block = latest_on_chain - CONFIRMATION_BLOCKS

                if self.last_processed_block >= target_block:
                    logger.info(f"Chain is synced up to block {self.last_processed_block}. Waiting for new blocks...")
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                # --- Reorg Detection --- #
                if self.last_processed_block_hash:
                    header = self.connector.get_block_header(self.last_processed_block + 1)
                    if header and header.get('parentHash').hex() != self.last_processed_block_hash:
                        self.last_processed_block = self._handle_reorg(self.last_processed_block)
                        continue # Restart loop from the safe block

                # Determine the range of blocks to process in this batch
                from_block = self.last_processed_block + 1
                # Process in chunks to avoid overwhelming the RPC node
                to_block = min(target_block, from_block + self.config['block_batch_size'] - 1)

                self.process_block_range(from_block, to_block)

                # Update state to the last block we processed in this batch
                last_processed_header = self.connector.get_block_header(to_block)
                if last_processed_header:
                    self.last_processed_block = to_block
                    self.last_processed_block_hash = last_processed_header.get('hash').hex()
                    self._save_state()
                else:
                    logger.warning(f"Could not fetch header for block {to_block} to update state. Retrying in next cycle.")

            except ConnectionError as e:
                logger.critical(f"A critical connection error occurred: {e}. The script cannot continue.")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
                time.sleep(POLL_INTERVAL_SECONDS * 2) # Longer sleep on unexpected errors


if __name__ == '__main__':
    # Example usage:
    # This simulation will listen to WETH 'Transfer' events on the Sepolia testnet,
    # treating them as 'deposit' events for a fictional bridge.

    # A minimal ABI for the ERC-20 Transfer event.
    ERC20_TRANSFER_ABI = json.loads('[
        {
            "anonymous": false,
            "inputs": [
                {"indexed": true, "name": "from", "type": "address"},
                {"indexed": true, "name": "to", "type": "address"},
                {"indexed": false, "name": "value", "type": "uint256"}
            ],
            "name": "Transfer",
            "type": "event"
        }
    ]')

    # --- Configuration from Environment Variables --- #
    # Create a .env file in the same directory with these values
    # EXAMPLE .env file:
    # RPC_URL="https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID"
    # CONTRACT_ADDRESS="0x7b79995e5f793A07Bc00c21412e50Ea00A78982e" # Example: WETH on Sepolia
    # START_BLOCK=5500000

    listener_config = {
        'rpc_url': os.getenv('RPC_URL'),
        'contract_address': Web3.to_checksum_address(os.getenv('CONTRACT_ADDRESS')),
        'contract_abi': ERC20_TRANSFER_ABI,
        'start_block': int(os.getenv('START_BLOCK', '5500000')), # A recent block on Sepolia
        'block_batch_size': 100, # Process 100 blocks at a time
        'oracle_api_endpoint': 'https://httpbin.org/post' # A public test endpoint that echoes POST requests
    }

    if not all([listener_config['rpc_url'], listener_config['contract_address']]):
        logger.critical("RPC_URL and CONTRACT_ADDRESS must be set in the .env file.")
    else:
        event_handler = CrossChainEventHandler(listener_config)
        event_handler.run()
