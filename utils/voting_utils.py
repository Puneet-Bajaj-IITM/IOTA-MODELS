
from datetime import datetime, UTC
import asyncio
from models.models import ModelVote, ModelRegistry
from textwrap import dedent
from iota_utils import mint_nft_with_ipfs
import time


class ModelVotingManager:
    def __init__(self, matrix_client, ipfs_client, account, db, MATRIX_PASSWORD, VOTING_ROOMS, VOTING_DURATION):
        self.matrix_client = matrix_client
        self.account = account
        self.ipfs_client = ipfs_client
        self.matrix_password = MATRIX_PASSWORD
        self.db = db
        self.voting_rooms = VOTING_ROOMS 
        self.voting_duration = VOTING_DURATION 

    async def count_votes_for_model(self, model_name, model_id):
        """
        Count votes for a specific model using Matrix room messages

        Args:
            model_name (str): Name of the model
            model_id (str): Unique identifier for the model proposal

        Returns:
            bool: True if model is approved, False if rejected
        """
        if not self.matrix_client.logged_in:
            await self.matrix_client.login(self.matrix_password)
        # Create voting session
        voting_session = ModelVote( # type: ignore
            model_name=model_name,
            yes_votes=0,
            no_votes=0,
            voting_start=datetime.now(UTC)
        )
        self.db.session.add(voting_session)
        self.db.session.commit()

        # Broadcast voting proposal
        await self.broadcast_voting_message({
            'model_name': model_name,
            'model_id': model_id
        })

        time.sleep(self.voting_duration) 

        for room_id in self.voting_rooms:
            try:
                # Retrieve recent room messages
                response = await self.matrix_client.room_messages(
                    room_id, 
                    start=''
                )
                print(response)

                # Process votes in these messages
                for event in response.chunk:
                    # Check if this is a vote for our specific model
                    if self.is_valid_vote(event, model_id):
                        self.process_single_vote(
                            voting_session, 
                            event
                        )

            except Exception as e:
                print(f"Error retrieving votes from room {room_id}: {e}")

        # Finalize voting
        return self.finalize_voting(voting_session, model_name)

    def is_valid_vote(self, event, model_id):
        """
        Validate if the message is a valid vote for the model

        Args:
            event (RoomMessageText): Matrix room message event
            model_id (str): Model identifier

        Returns:
            bool: True if valid vote, False otherwise
        """
        # Example vote format: "yes ModelID" or "no ModelID"
        body = event.body.lower().strip()
        return (body.startswith('yes ') or body.startswith('no ')) and \
               body.split()[-1].strip() == model_id

    def process_single_vote(self, voting_session, event):
        """
        Process an individual vote

        Args:
            voting_session (ModelVote): Current voting session
            event (RoomMessageText): Matrix room message event
        """
        body = event.body.lower().strip()

        if body.startswith('yes'):
            voting_session.yes_votes += 1
        elif body.startswith('no'):
            voting_session.no_votes += 1

        self.db.session.commit()

    def finalize_voting(self, voting_session, model_name):
        """
        Finalize voting and process model

        Args:
            voting_session (ModelVote): Voting session details
            model_name (str): Name of the model

        Returns:
            bool: True if model approved, False if rejected
        """
        # Retrieve the model
        model = ModelRegistry.query.filter_by(model_name=model_name).first()

        if not model:
            print(f"Model {model_name} not found")
            return False

        # Determine voting outcome
        is_approved = voting_session.yes_votes > voting_session.no_votes

        if is_approved:
            try:
                # Mint NFT and update model status
                nft_id = mint_nft_with_ipfs(
                    account=self.account, 
                    ipfs_client=self.ipfs_client, 
                    metadata=model
                )
                
                model.status = 'approved'
                model.nft_id = nft_id
                
            except Exception as e:
                print(f"Model processing failed: {e}")
                is_approved = False
                model.status = 'rejected'
        else:
            model.status = 'rejected'

        # Clean up voting session
        self.db.session.delete(voting_session)
        self.db.session.commit()

        # Broadcast results
        asyncio.create_task(
            self.broadcast_approval_result(
                model_name, 
                is_approved
            )
        )

        return is_approved

    async def broadcast_voting_message(self, model_data):
        """
        Broadcast model voting message to Matrix rooms

        Args:
            model_data (dict): Model voting details
        """
        
        voting_message = dedent(f"""
            MODEL VOTING PROPOSAL
            --------------------
            Model Name: {model_data['model_name']}
            Model ID: {model_data['model_id']}
            
            VOTING INSTRUCTIONS:
            - Reply 'yes {model_data['model_id']}' to approve this model
            - Reply 'no {model_data['model_id']}' to reject this model
            - Voting closes in 5 minutes
        """)
        
        for room_id in self.voting_rooms:
            try:
                await self.matrix_client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": voting_message
                    }
                )
            except Exception as e:
                print(f"Failed to broadcast voting message: {e}")

    async def broadcast_approval_result(self, model_name, approved):
        """
        Broadcast model voting results

        Args:
            model_name (str): Name of the model
            approved (bool): Whether the model was approved
        """
        
        result_message = dedent(f"""
            MODEL VOTING RESULT
            -------------------
            Model: {model_name}
            Status: {"APPROVED" if approved else "REJECTED"}
        """)
        
        for room_id in self.voting_rooms:
            try:
                await self.matrix_client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": result_message
                    }
                )
            except Exception as e:
                print(f"Failed to broadcast result: {e}")

