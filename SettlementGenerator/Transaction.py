class Transaction:
    def __init__(self, transaction_id, cash_instruction, bond_instruction):
        self.transaction_id = transaction_id
        self.cash_instruction = cash_instruction  # Cash leg
        self.bond_instruction = bond_instruction  # Bond leg

    def __str__(self):
        return f"Transaction({self.transaction_id})"