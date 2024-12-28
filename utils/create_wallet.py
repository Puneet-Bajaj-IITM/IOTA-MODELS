import os
import shutil
from dotenv import load_dotenv
from iota_sdk import ClientOptions, CoinType, StrongholdSecretManager
from iota_sdk.wallet.wallet import Wallet

load_dotenv('.env.example')

# Removes the directory and all its contents
shutil.rmtree('example-walletdb')
os.remove('example.stronghold')

node_url = os.environ.get('NODE_URL', 'https://api.testnet.shimmer.network')
client_options = ClientOptions(nodes=[node_url])

ISSUER_ID = os.getenv('ISSUER_ID')

# Shimmer coin type
coin_type = CoinType.SHIMMER

for env_var in ['STRONGHOLD_PASSWORD', 'MNEMONIC']:
    if env_var not in os.environ:
        raise Exception(f".env {env_var} is undefined, see .env.example")

secret_manager = StrongholdSecretManager(
    os.environ['STRONGHOLD_SNAPSHOT_PATH'], 
    os.environ['STRONGHOLD_PASSWORD']
)


wallet = Wallet(
    os.environ['WALLET_DB_PATH'], 
    client_options, coin_type,
    secret_manager
)

wallet.store_mnemonic(os.environ['MNEMONIC'])

account = wallet.create_account('Alice')
print("Account created:", account.get_metadata())