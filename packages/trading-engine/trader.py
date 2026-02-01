"""
Trading Engine - Swaps via 1inch API Aggregator
"""
import asyncio
import os
import time
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional

import httpx
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.signers.local import LocalAccount

from models import (
    Token, SwapQuote, SwapTransaction, TradeOrder, TradeResult,
    TradeStatus, TradeDirection, TradingConfig, ChainId
)


class OneInchError(Exception):
    """Erreur spécifique à l'API 1inch"""
    def __init__(self, message: str, status_code: int = 0, error_code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class InsufficientBalanceError(Exception):
    """Balance insuffisante pour le trade"""
    pass


class SlippageExceededError(Exception):
    """Slippage dépassé"""
    pass


class Trader:
    """
    Trading Engine pour swaps EVM via 1inch Aggregator
    
    Supporte:
    - Multi-chain (ETH, BSC, Polygon, Arbitrum, etc.)
    - Quotes et swaps via 1inch Fusion/Classic
    - Gas estimation EIP-1559
    - Slippage protection
    """
    
    # Adresses natives par chain
    NATIVE_TOKEN = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    
    # WETH addresses par chain
    WRAPPED_NATIVE = {
        1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",      # WETH
        56: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",     # WBNB
        137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",    # WMATIC
        42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH Arbitrum
        10: "0x4200000000000000000000000000000000000006",     # WETH Optimism
        8453: "0x4200000000000000000000000000000000000006",   # WETH Base
        43114: "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", # WAVAX
    }
    
    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._web3_instances: dict[int, Web3] = {}
        self._account: Optional[LocalAccount] = None
    
    async def __aenter__(self):
        await self._init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _init_client(self):
        """Initialise le client HTTP"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.config.oneinch_api_key:
            headers["Authorization"] = f"Bearer {self.config.oneinch_api_key}"
        
        self._http_client = httpx.AsyncClient(
            base_url=self.config.oneinch_base_url,
            headers=headers,
            timeout=httpx.Timeout(self.config.quote_timeout),
        )
    
    async def close(self):
        """Ferme les connexions"""
        if self._http_client:
            await self._http_client.aclose()
    
    def _get_web3(self, chain_id: int) -> Web3:
        """Obtient une instance Web3 pour une chain"""
        if chain_id not in self._web3_instances:
            rpc_url = self.config.rpc_urls.get(chain_id)
            if not rpc_url:
                # URLs publiques par défaut
                default_rpcs = {
                    1: "https://eth.llamarpc.com",
                    56: "https://bsc-dataseed.binance.org",
                    137: "https://polygon-rpc.com",
                    42161: "https://arb1.arbitrum.io/rpc",
                    10: "https://mainnet.optimism.io",
                    8453: "https://mainnet.base.org",
                    43114: "https://api.avax.network/ext/bc/C/rpc",
                }
                rpc_url = default_rpcs.get(chain_id)
                if not rpc_url:
                    raise ValueError(f"No RPC URL for chain {chain_id}")
            
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            # Middleware POA pour certaines chains
            if chain_id in [56, 137]:
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            self._web3_instances[chain_id] = w3
        
        return self._web3_instances[chain_id]
    
    def set_account(self, private_key: str):
        """Configure le compte pour signer les transactions"""
        self._account = Account.from_key(private_key)
    
    @property
    def wallet_address(self) -> Optional[str]:
        """Adresse du wallet configuré"""
        return self._account.address if self._account else None
    
    # =========================================================================
    # 1inch API Methods
    # =========================================================================
    
    async def _api_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        json_data: Optional[dict] = None
    ) -> dict:
        """Requête générique à l'API 1inch"""
        if not self._http_client:
            await self._init_client()
        
        try:
            if method == "GET":
                response = await self._http_client.get(endpoint, params=params)
            else:
                response = await self._http_client.post(endpoint, json=json_data, params=params)
            
            if response.status_code == 429:
                raise OneInchError("Rate limit exceeded", 429, "RATE_LIMIT")
            
            data = response.json()
            
            if response.status_code >= 400:
                error_msg = data.get("description", data.get("error", "Unknown error"))
                raise OneInchError(error_msg, response.status_code)
            
            return data
            
        except httpx.TimeoutException:
            raise OneInchError("Request timeout", 0, "TIMEOUT")
        except httpx.RequestError as e:
            raise OneInchError(f"Request failed: {e}", 0, "REQUEST_ERROR")
    
    async def get_tokens(self, chain_id: int) -> dict[str, Token]:
        """Liste des tokens supportés sur une chain"""
        data = await self._api_request(
            "GET",
            f"/swap/v6.0/{chain_id}/tokens"
        )
        
        tokens = {}
        for addr, info in data.get("tokens", {}).items():
            tokens[addr.lower()] = Token(
                address=addr,
                symbol=info["symbol"],
                decimals=info["decimals"],
                chain_id=chain_id,
                name=info.get("name"),
                logo_uri=info.get("logoURI"),
            )
        return tokens
    
    async def get_quote(
        self,
        chain_id: int,
        src_token: Token,
        dst_token: Token,
        amount: int,
        include_protocols: bool = True,
    ) -> SwapQuote:
        """
        Obtient une quote pour un swap
        
        Args:
            chain_id: ID de la chain
            src_token: Token source
            dst_token: Token destination
            amount: Montant en wei
            include_protocols: Inclure les détails de routing
        
        Returns:
            SwapQuote avec prix et estimation
        """
        params = {
            "src": src_token.address,
            "dst": dst_token.address,
            "amount": str(amount),
            "includeProtocols": str(include_protocols).lower(),
            "includeGas": "true",
        }
        
        data = await self._api_request(
            "GET",
            f"/swap/v6.0/{chain_id}/quote",
            params=params
        )
        
        dst_amount = int(data["dstAmount"])
        gas_estimate = int(data.get("gas", 0))
        
        # Calcul du prix
        src_dec = src_token.from_wei(amount)
        dst_dec = dst_token.from_wei(dst_amount)
        price = dst_dec / src_dec if src_dec > 0 else Decimal("0")
        
        return SwapQuote(
            src_token=src_token,
            dst_token=dst_token,
            src_amount=amount,
            dst_amount=dst_amount,
            protocols=data.get("protocols", []),
            gas_estimate=gas_estimate,
            price=price,
            quoted_at=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(seconds=30),
        )
    
    async def get_swap_tx(
        self,
        chain_id: int,
        src_token: Token,
        dst_token: Token,
        amount: int,
        from_address: str,
        slippage: Decimal = Decimal("1.0"),
        receiver: Optional[str] = None,
    ) -> SwapTransaction:
        """
        Génère une transaction de swap prête à être signée
        
        Args:
            chain_id: ID de la chain
            src_token: Token source
            dst_token: Token destination
            amount: Montant en wei
            from_address: Adresse qui exécute le swap
            slippage: Slippage toléré en %
            receiver: Adresse de réception (défaut: from_address)
        
        Returns:
            SwapTransaction prête à signer
        """
        if slippage > self.config.max_slippage:
            raise SlippageExceededError(
                f"Slippage {slippage}% exceeds max {self.config.max_slippage}%"
            )
        
        params = {
            "src": src_token.address,
            "dst": dst_token.address,
            "amount": str(amount),
            "from": from_address,
            "slippage": str(float(slippage)),
            "includeGas": "true",
        }
        
        if receiver and receiver != from_address:
            params["receiver"] = receiver
        
        data = await self._api_request(
            "GET",
            f"/swap/v6.0/{chain_id}/swap",
            params=params
        )
        
        tx_data = data["tx"]
        
        # Quote incluse dans la réponse
        quote = SwapQuote(
            src_token=src_token,
            dst_token=dst_token,
            src_amount=amount,
            dst_amount=int(data["dstAmount"]),
            gas_estimate=int(tx_data.get("gas", 0)),
            price=Decimal(str(data.get("dstAmount", 0))) / Decimal(str(amount)) if amount > 0 else Decimal("0"),
        )
        
        return SwapTransaction(
            to=tx_data["to"],
            data=tx_data["data"],
            value=int(tx_data.get("value", 0)),
            gas=int(tx_data.get("gas", 300000)),
            quote=quote,
            chain_id=chain_id,
        )
    
    # =========================================================================
    # Balance & Allowance
    # =========================================================================
    
    async def get_balance(
        self, 
        chain_id: int, 
        address: str, 
        token: Optional[Token] = None
    ) -> int:
        """
        Obtient le balance d'un token
        
        Args:
            chain_id: ID de la chain
            address: Adresse du wallet
            token: Token (None pour balance native)
        
        Returns:
            Balance en wei
        """
        w3 = self._get_web3(chain_id)
        
        if token is None or token.is_native:
            return w3.eth.get_balance(Web3.to_checksum_address(address))
        
        # ERC20 balance
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token.address),
            abi=erc20_abi
        )
        
        return contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
    
    async def get_allowance(
        self,
        chain_id: int,
        token: Token,
        owner: str,
        spender: str,
    ) -> int:
        """Vérifie l'allowance ERC20"""
        if token.is_native:
            return 2**256 - 1  # Pas besoin d'approval pour ETH
        
        w3 = self._get_web3(chain_id)
        
        erc20_abi = [
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token.address),
            abi=erc20_abi
        )
        
        return contract.functions.allowance(
            Web3.to_checksum_address(owner),
            Web3.to_checksum_address(spender)
        ).call()
    
    async def approve_token(
        self,
        chain_id: int,
        token: Token,
        spender: str,
        amount: Optional[int] = None,
    ) -> str:
        """
        Approve un token pour un spender
        
        Args:
            chain_id: ID de la chain
            token: Token à approve
            spender: Adresse autorisée à spend
            amount: Montant (défaut: max uint256)
        
        Returns:
            Transaction hash
        """
        if not self._account:
            raise ValueError("No account configured. Call set_account() first.")
        
        if token.is_native:
            return ""  # Pas besoin d'approval
        
        w3 = self._get_web3(chain_id)
        
        if amount is None:
            amount = 2**256 - 1  # Max approval
        
        erc20_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token.address),
            abi=erc20_abi
        )
        
        # Build transaction
        nonce = w3.eth.get_transaction_count(self._account.address)
        
        tx = contract.functions.approve(
            Web3.to_checksum_address(spender),
            amount
        ).build_transaction({
            "chainId": chain_id,
            "from": self._account.address,
            "nonce": nonce,
            "gas": 100000,
        })
        
        # Add gas price
        tx = await self._add_gas_price(w3, tx)
        
        # Sign and send
        signed_tx = self._account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        return tx_hash.hex()
    
    # =========================================================================
    # Execute Trade
    # =========================================================================
    
    async def _add_gas_price(self, w3: Web3, tx: dict) -> dict:
        """Ajoute les paramètres de gas à une transaction"""
        gas_settings = self.config.gas_settings
        
        if gas_settings.use_eip1559:
            try:
                # EIP-1559
                base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
                max_priority = w3.to_wei(gas_settings.max_priority_fee_gwei, "gwei")
                max_fee = min(
                    base_fee * 2 + max_priority,
                    w3.to_wei(gas_settings.max_gas_price_gwei, "gwei")
                )
                
                tx["maxFeePerGas"] = max_fee
                tx["maxPriorityFeePerGas"] = max_priority
                return tx
            except Exception:
                pass  # Fallback to legacy
        
        # Legacy gas price
        gas_price = min(
            w3.eth.gas_price,
            w3.to_wei(gas_settings.max_gas_price_gwei, "gwei")
        )
        tx["gasPrice"] = gas_price
        return tx
    
    async def execute_swap(
        self,
        order: TradeOrder,
        wait_confirmation: bool = True,
    ) -> TradeResult:
        """
        Exécute un swap complet
        
        Args:
            order: Ordre de trade
            wait_confirmation: Attendre la confirmation on-chain
        
        Returns:
            TradeResult avec détails de l'exécution
        """
        if not self._account:
            raise ValueError("No account configured. Call set_account() first.")
        
        start_time = time.time()
        order.status = TradeStatus.PENDING
        
        try:
            # 1. Vérifier le balance
            balance = await self.get_balance(
                order.chain_id, 
                self._account.address, 
                order.src_token
            )
            
            if balance < order.src_amount:
                raise InsufficientBalanceError(
                    f"Insufficient balance: {order.src_token.from_wei(balance)} "
                    f"< {order.src_token.from_wei(order.src_amount)} {order.src_token.symbol}"
                )
            
            # 2. Vérifier/faire l'approval si nécessaire
            if not order.src_token.is_native:
                # Get 1inch router address
                router_data = await self._api_request(
                    "GET",
                    f"/swap/v6.0/{order.chain_id}/approve/spender"
                )
                router_address = router_data["address"]
                
                allowance = await self.get_allowance(
                    order.chain_id,
                    order.src_token,
                    self._account.address,
                    router_address
                )
                
                if allowance < order.src_amount:
                    print(f"Approving {order.src_token.symbol}...")
                    approve_hash = await self.approve_token(
                        order.chain_id,
                        order.src_token,
                        router_address
                    )
                    # Wait for approval
                    w3 = self._get_web3(order.chain_id)
                    w3.eth.wait_for_transaction_receipt(approve_hash, timeout=60)
            
            # 3. Get swap transaction
            order.status = TradeStatus.QUOTED
            swap_tx = await self.get_swap_tx(
                chain_id=order.chain_id,
                src_token=order.src_token,
                dst_token=order.dst_token,
                amount=order.src_amount,
                from_address=self._account.address,
                slippage=order.slippage,
            )
            
            # 4. Build and sign transaction
            w3 = self._get_web3(order.chain_id)
            nonce = w3.eth.get_transaction_count(self._account.address)
            
            # Apply gas buffer
            gas_limit = int(swap_tx.gas * float(self.config.gas_settings.gas_limit_multiplier))
            
            tx = {
                "to": Web3.to_checksum_address(swap_tx.to),
                "data": swap_tx.data,
                "value": swap_tx.value,
                "gas": gas_limit,
                "nonce": nonce,
                "chainId": order.chain_id,
            }
            
            tx = await self._add_gas_price(w3, tx)
            
            # 5. Sign and send
            signed_tx = self._account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            order.tx_hash = tx_hash.hex()
            order.status = TradeStatus.SUBMITTED
            
            # 6. Wait for confirmation
            gas_used = 0
            gas_price = tx.get("gasPrice", tx.get("maxFeePerGas", 0))
            
            if wait_confirmation:
                receipt = w3.eth.wait_for_transaction_receipt(
                    tx_hash, 
                    timeout=self.config.tx_timeout
                )
                
                if receipt["status"] == 1:
                    order.status = TradeStatus.CONFIRMED
                else:
                    order.status = TradeStatus.FAILED
                    order.error_message = "Transaction reverted"
                
                gas_used = receipt["gasUsed"]
                gas_price = receipt.get("effectiveGasPrice", gas_price)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return TradeResult(
                order=order,
                success=order.status == TradeStatus.CONFIRMED,
                tx_hash=order.tx_hash,
                src_amount_spent=order.src_amount,
                dst_amount_received=swap_tx.quote.dst_amount if swap_tx.quote else 0,
                gas_used=gas_used,
                gas_price=gas_price,
                total_gas_cost=gas_used * gas_price,
                execution_time_ms=execution_time,
                confirmed_at=datetime.utcnow() if wait_confirmation else None,
            )
            
        except Exception as e:
            order.status = TradeStatus.FAILED
            order.error_message = str(e)
            
            return TradeResult(
                order=order,
                success=False,
                error=str(e),
                error_code=getattr(e, "error_code", "UNKNOWN"),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    async def swap(
        self,
        chain_id: int,
        src_token_address: str,
        dst_token_address: str,
        amount_human: Decimal,
        slippage: Decimal = Decimal("1.0"),
    ) -> TradeResult:
        """
        Méthode simplifiée pour exécuter un swap
        
        Args:
            chain_id: ID de la chain (1=ETH, 56=BSC, etc.)
            src_token_address: Adresse du token source
            dst_token_address: Adresse du token destination
            amount_human: Montant human-readable
            slippage: Slippage en %
        
        Returns:
            TradeResult
        """
        if not self._account:
            raise ValueError("No account configured. Call set_account() first.")
        
        # Get token info
        tokens = await self.get_tokens(chain_id)
        
        src_token = tokens.get(src_token_address.lower())
        dst_token = tokens.get(dst_token_address.lower())
        
        if not src_token:
            # Token natif
            src_token = Token(
                address=src_token_address,
                symbol="ETH",
                decimals=18,
                chain_id=chain_id,
            )
        
        if not dst_token:
            raise ValueError(f"Unknown destination token: {dst_token_address}")
        
        # Create order
        order = TradeOrder(
            id=str(uuid.uuid4()),
            wallet_address=self._account.address,
            chain_id=chain_id,
            src_token=src_token,
            dst_token=dst_token,
            src_amount=src_token.to_wei(amount_human),
            slippage=slippage,
        )
        
        return await self.execute_swap(order)


# =============================================================================
# CLI / Example Usage
# =============================================================================

async def main():
    """Example usage"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    config = TradingConfig(
        oneinch_api_key=os.getenv("ONEINCH_API_KEY"),
    )
    
    async with Trader(config) as trader:
        # Set wallet from private key
        private_key = os.getenv("WALLET_PRIVATE_KEY")
        if private_key:
            trader.set_account(private_key)
            print(f"Wallet: {trader.wallet_address}")
        
        # Example: Get quote for ETH -> USDC on Ethereum
        eth = Token(
            address="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            symbol="ETH",
            decimals=18,
            chain_id=1,
        )
        
        usdc = Token(
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            symbol="USDC",
            decimals=6,
            chain_id=1,
        )
        
        # Get quote for 0.1 ETH
        amount = eth.to_wei(Decimal("0.1"))
        
        print("\nGetting quote for 0.1 ETH -> USDC...")
        quote = await trader.get_quote(
            chain_id=1,
            src_token=eth,
            dst_token=usdc,
            amount=amount,
        )
        
        print(f"Quote: {quote.src_amount_human} ETH -> {quote.dst_amount_human} USDC")
        print(f"Price: 1 ETH = {quote.price} USDC")
        print(f"Gas estimate: {quote.gas_estimate}")


if __name__ == "__main__":
    asyncio.run(main())
