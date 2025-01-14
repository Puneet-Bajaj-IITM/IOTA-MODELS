
from db_models.models import ModelRegistry
from textwrap import dedent
from utils.iota_utils import mint_nft_with_ipfs
import torch


class ModelVotingManager:
    def __init__(self, app, matrix_client, ipfs_client, account, db, MATRIX_PASSWORD, VOTING_ROOMS, VOTING_DURATION):
        self.matrix_client = matrix_client
        self.account = account
        self.ipfs_client = ipfs_client
        self.matrix_password = MATRIX_PASSWORD
        self.app = app
        self.db = db
        self.voting_rooms = VOTING_ROOMS 
        self.voting_duration = VOTING_DURATION 
    
    async def matrix_login(self):
        print('logging in to matrix')
        if not self.matrix_client.logged_in:
            await self.matrix_client.login(self.matrix_password)
            print('Done login to matrix')
        else :
            print('Already logged in')

    async def count_votes_for_model(self, model_id, voting_session):
        """
        Count votes for a specific model using Matrix room messages
        """
        with self.app.app_context():
            yes_votes, no_votes = 0, 0

            for room_id in self.voting_rooms:
                try:
                    # Retrieve recent room messages
                    response = await self.matrix_client.room_messages(
                        room_id, 
                        start=''
                    )
                   

                    # Process votes in these messages
                    for event in response.chunk:
                        # Check if this is a vote for our specific model
                        if self.is_valid_vote(event, model_id):
                            print('processing single vote')
                            if not self.db.session.object_session(voting_session):
                                self.db.session.add(voting_session)

                            yes, no = self.process_single_vote(
                                voting_session, 
                                event
                            )
                            yes_votes += yes
                            no_votes += no
                    return yes_votes, no_votes

                except Exception as e:
                    
                    print(f"Error retrieving votes from room {room_id}: {e}")
                    return 0, 1


    def is_valid_vote(self, event, model_id):
        """
        Validate if the message is a valid vote for the model
        """
        # Example vote format: "yes ModelID" or "no ModelID"
        print(event)
        body = event.body.lower().strip()
        res = (body.startswith('yes ') or body.startswith('no ')) and \
               body.split()[-1].strip() == model_id
        print(res)
        return res

    def process_single_vote(self, voting_session, event):
        """
        Process an individual vote
        """
        body = event.body.lower().strip()
        yes , no = 0, 0

        # Ensure voting_session is attached to the session
        if body.startswith('yes'):
            yes += 1
        elif body.startswith('no'):
            no += 1
                
        return yes, no


    def finalize_voting(self, yes_votes, no_votes, model_name, student_model, update_teacher_model):
        """
        Finalize voting and process model
        """
        print('Finalizing voting')
        with self.app.app_context():
            # Retrieve the model
            model = ModelRegistry.query.filter_by(model_name=model_name).first()

            if not model:
                print(f"Model {model_name} not found")
                return False

            # Determine voting outcome
            is_approved = yes_votes > no_votes


            if is_approved:
                try:
                    teacher_model, global_model = update_teacher_model()
                    student_file_path = 'student_model.pt'
                    teacher_file_path = 'teacher_model.pt'
                    global_file_path = 'global_model.pt'

                    # Save models for testing (consider moving model creation elsewhere for production)
                    torch.save(student_model, student_file_path)
                    torch.save(teacher_model, teacher_file_path)
                    torch.save(global_model, global_file_path)

                    print('Starting IPFS upload')
                    model.student_model_cid =  retrieve_hash(self.ipfs_client.add(student_file_path))
                    model.teacher_model_cid = retrieve_hash(self.ipfs_client.add(teacher_file_path))
                    model.global_model_cid =  retrieve_hash(self.ipfs_client.add(global_file_path))
                    print('Minting NFt')

                    # Mint NFT and update model status
                    nft_id = mint_nft_with_ipfs(
                        account=self.account,
                        metadata=model.to_json()

                    )

                    
                    
                    model.status = 'approved'
                    model.nft_id = nft_id
                    self.db.session.commit()
                
                    
                    
                except Exception as e:
                    print(f"Model processing failed: {e}")
                    is_approved = False
                    model.status = 'rejected'
                    self.db.session.commit()
            else:
                model.status = 'rejected'
                student_model = torch.load('student_model.pt')
                self.db.session.commit()


        # Clean up voting session
        self.db.session.commit()

        return is_approved

    async def broadcast_voting_message(self, model_data):
        """
        Broadcast model voting message to Matrix rooms
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


def retrieve_hash(x):
    if isinstance(x, list):  # Check if x is a list
        x1 = x[0]['Hash']  # If it's a list, access the first element and then the Hash
    else:
        x1 = x['Hash']  # If it's not a list, access the Hash directly
    return x1