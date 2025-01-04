from iota_sdk import utf8_to_hex, MintNftParams
from iota_sdk.wallet.wallet import Wallet
from iota_sdk.utils import Utils
from ipfs_utils import upload_metadata_to_ipfs
import os

def load_wallet(name):

    wallet = Wallet(os.environ['WALLET_DB_PATH'])

    if 'STRONGHOLD_PASSWORD' not in os.environ:
        raise Exception(".env STRONGHOLD_PASSWORD is undefined, see .env.example")

    wallet.set_stronghold_password(os.environ["STRONGHOLD_PASSWORD"])

    account = wallet.get_account(name)
    account.sync()
    return wallet, account


def mint_nft_with_ipfs(ipfs_client, account, metadata: dict):
    """Mint a single NFT with metadata stored on IPFS."""
    print("Uploading metadata to IPFS...")
    cid = upload_metadata_to_ipfs(ipfs_client, metadata)
    cid_hex = utf8_to_hex(cid)

    print("Sending NFT minting transaction...")
    params = MintNftParams(immutableMetadata=cid_hex)
    transaction = account.mint_nfts([params])

    # Wait for transaction inclusion
    block_id = account.retry_transaction_until_included(
        transaction.transactionId)
    print(f'Block sent: {os.environ["EXPLORER_URL"]}/block/{block_id}')

    # Extract NFT ID
    essence = transaction.payload["essence"]
    for outputIndex, output in enumerate(essence["outputs"]):
        if output["type"] == 6 and output[
                "nftId"] == '0x0000000000000000000000000000000000000000000000000000000000000000':
            outputId = Utils.compute_output_id(transaction.transactionId,
                                               outputIndex)
            nftId = Utils.compute_nft_id(outputId)
            print(f'New minted NFT ID: {nftId}')
    return cid, nftId # type: ignore


def mint_nft_collection_with_ipfs(ipfs_client, wallet, account, ISSUER_ID, metadata_list: list, issuer_nft_id):
    """Mint a collection of NFTs with their metadata stored on IPFS."""
    print(f"Starting minting of {len(metadata_list)} NFTs...")
    minted_nft_ids = []
    bech32_hrp = wallet.get_client().get_bech32_hrp()
    issuer = Utils.nft_id_to_bech32(issuer_nft_id, bech32_hrp)

    for metadata in metadata_list:
        cid = upload_metadata_to_ipfs(ipfs_client, metadata)
        cid_hex = utf8_to_hex(cid)
        params = MintNftParams(immutableMetadata=cid_hex, issuer=issuer)

        transaction = account.mint_nfts([params])
        block_id = account.retry_transaction_until_included(
            transaction.transactionId)
        print(f'Block sent: {os.environ["EXPLORER_URL"]}/block/{block_id}')

        # Extract NFT ID
        essence = transaction.payload["essence"]
        for outputIndex, output in enumerate(essence["outputs"]):
            if output["type"] == 6 and output["nftId"] == ISSUER_ID:
                outputId = Utils.compute_output_id(transaction.transactionId,
                                                   outputIndex)
                nftId = Utils.compute_nft_id(outputId)
                minted_nft_ids.append({"cid": cid, "nftId": nftId})
                print(f'New minted NFT ID: {nftId}')
    return minted_nft_ids