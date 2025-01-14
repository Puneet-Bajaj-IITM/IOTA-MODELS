
# import ipfsApi

# IPFS_SERVER_IP='179.61.246.8'
# IPFS_SERVER_PORT=5001
# student_file_path =  'student_model.pt'

# ipfs_client = ipfsApi.Client(IPFS_SERVER_IP, IPFS_SERVER_PORT)

# x = ipfs_client.add(student_file_path)

# print(x)

from utils.iota_utils import mint_nft_with_ipfs, load_wallet

account = load_wallet(name='alice')[1]
x = mint_nft_with_ipfs(account, json.dumps('{}'))






# from nio import AsyncClient
# import asyncio

# matrix_client = AsyncClient("https://socialxmatch.com", "@bot_user:socialxmatch.com")

# async def fun():
#     if not matrix_client.logged_in:
#         res = await matrix_client.login("Hosting+123321")
#         print(res)
#         print('Done login to matrix')
#     else :
#         print('Already logged in')

#     res = await matrix_client.room_send(
#         room_id="!4JVUuZfXSS0XfgU9:socialxmatch.com",
#         message_type="m.room.message",
#         content={
#             "msgtype": "m.text",
#             "body": 'voting_message'
#         }
#     )
#     print(res)

# asyncio.run(fun())