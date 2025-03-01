class Instruction:
    def __init__(self, unique_id, mother_id, security_type, amount,
                 is_child, status, role, link_code, from_account, to_account, timestamp):
        self.unique_id = unique_id
        self.mother_id = mother_id      # Always "DUMMY"
        self.security_type = security_type
        self.amount = amount
        self.is_child = is_child        # Always False here.
        self.status = status
        self.role = role                # "Cash" or "Bond" leg identifier
        self.link_code = link_code      # Shared between the two legs
        self.from_account = from_account  # Account sending the amount
        self.to_account = to_account      # Account receiving the amount
        self.timestamp = timestamp      # Each instruction gets its own timestamp

    def __str__(self):
        return (f"Instruction({self.unique_id}, motherID: {self.mother_id}, "
                f"{self.security_type}, {self.amount}, {self.is_child}, {self.status}, "
                f"role: {self.role}, link_code: {self.link_code}, "
                f"from_account: {self.from_account.account_id}, "
                f"to_account: {self.to_account.account_id}, "
                f"timestamp: {self.timestamp})")


    #for generator