import datetime
import random
from typing import List
import pandas as pd
from mesa import Agent, Model
import time

class AccountAgent(Agent):
    def __init__(self, accountID, model, participant, cashBalance, creditLimit):
        super().__init__(model)
        self.accountID = accountID
        self.state = 'Pending'
        self.participant = participant
        self.cashBalance = cashBalance
        self.securities = {} #dictionary to store securities: (securityType: amount)
        self.creditLimit = creditLimit
        self.model.log_event(f"Account {accountID} created with balance {cashBalance} and credit limit {creditLimit}", accountID, is_transaction=False)

    def checkSufficientCash(self, amount):
        return self.cashBalance + self.creditLimit >= amount

    def checkSufficientSecurities(self, securityType: str, amount: float) -> bool:
        return self.securities.get(securityType, 0) >= amount

    def getCreditLimit(self):
        return self.creditLimit

    def getCashBalance(self):
        return self.cashBalance

    def updateSecurities(self, securityType: str, amount: float):
        current_amount = self.securities.get(securityType, 0)
        if current_amount + amount < 0:
            self.model.log_event(f"ERROR: Account {self.accountID} has insufficient securities of type {securityType}",
                                 self.accountID, is_transaction=False)
            return 0

        self.securities[securityType] = current_amount + amount
        self.model.log_event(
            f"Account {self.accountID} updated securities {securityType} by {amount}, new amount: {self.securities[securityType]}",
            self.accountID,
            is_transaction=False
        )
        return amount

    def updateCashBalance(self, amount: float):
        total_available = self.cashBalance + self.creditLimit
        if amount < 0 and total_available + amount < 0:  # Check if deducting more than available
            self.model.log_event(f"ERROR: Account {self.accountID} has insufficient funds", self.accountID,
                                 is_transaction=False)
            return 0

        if self.cashBalance + amount >= 0:
            self.cashBalance += amount
        else:
            remaining = amount + self.cashBalance
            self.cashBalance = 0
            self.creditLimit += remaining

        self.model.log_event(
            f"Account {self.accountID} updated cash balance by {amount}, new balance: {self.cashBalance}, new credit limit: {self.creditLimit}",
            self.accountID,
            is_transaction=False
        )
        return amount


    def end_account(self):
        if self.state == 'Ended':
            self.model.log_event(f"ERROR: Attempt to end an already ended Account {self.accountID}", self.accountID, is_transaction=False)
        else:
            self.model.log_event(f"Account {self.accountID} is ending", self.accountID, is_transaction=False)
            self.state = 'Ended'
            self.model.log_event(f"Account {self.accountID} ended", self.accountID, is_transaction=False)

class InstitutionAgent(Agent):

    def __init__(self, institutionID, model):
        super().__init__(model)
        self.institutionID = institutionID
        self.allow_partial: bool = True #default state allows partial
        self.accounts: List[AccountAgent] = []
        self.model.log_event(f"Institution {institutionID} created", institutionID, is_transaction=False)

    def opt_out_partial(self):
        if not self.allow_partial:
            self.model.log_event(f"ERROR: Institution {self.institutionID} already opted out of partial settlements", self.institutionID, is_transaction=False)
        else:
            self.allow_partial = False
            self.model.log_event(f"Institution {self.institutionID} opted out of partial settlements", self.institutionID, is_transaction=False)

    def opt_in_partial(self):
        if self.allow_partial:
            self.model.log_event(f"ERROR: Institution {self.institutionID} already opted in for partial settlements", self.institutionID, is_transaction=False)
        else:
            self.allow_partial = True
            self.model.log_event(f"Institution {self.institutionID} opted in for partial settlements", self.institutionID, is_transaction=False)


    def add_account(self, account:AccountAgent):
        if account in self.accounts:
            self.model.log_event(f"ERROR: Duplicate account addition attempt for Institution {self.institutionID}", self.institutionID, is_transaction=False)
        else:
            self.accounts.append(account)
            self.model.log_event(f"Institution {self.institutionID} added Account {account.accountID}", self.institutionID, is_transaction=False)

    def step(self):
        self.model.log_event(f"Institution {self.institutionID} stepping - Allow Partial: {self.allow_partial}", self.institutionID, is_transaction=False)    # Participants might modify their settings (randomly for testing)
        if random.random() < 0.1:
            if self.allow_partial:
                self.opt_out_partial()
            else:
                self.opt_in_partial()


class InstructionAgent:
    def __init__(self, uniqueID: str, motherID: str, securityType: str, amount: float, isChild: bool, status: str,
                 role: str, account: AccountAgent):
        self.uniqueID = uniqueID
        self.motherID = motherID
        self.securityType = securityType
        self.amount = amount
        self.isChild = isChild
        self.childInstructions: List['InstructionAgent'] = []
        self.status = status
        self.role = role  # seller/buyer
        self.account = account
        self.creation_time = datetime.datetime.now() # track creation time for timeout

    def createChildren(self):
        if self.role == "buyer" and not self.account.checkSufficientCash(self.amount):
            available_cash = self.account.getCashBalance() + self.account.getCreditLimit()
            if available_cash > 0:
                # Create buyer child instructions
                buyer_child1 = InstructionAgent(
                    f"{self.uniqueID}_1", self.uniqueID, self.securityType, available_cash, True,
                    "settled", "buyer", self.account)
                buyer_child2 = InstructionAgent(
                    f"{self.uniqueID}_2", self.uniqueID, self.securityType, self.amount - available_cash, True,
                    "pending", "buyer", self.account)

                # Update buyer's account for settled amount
                self.account.updateCashBalance(-available_cash)

                # Add child instructions to the model @ruben dont know what this should do tbh
                self.model.schedule.add(buyer_child1)
                self.model.schedule.add(buyer_child2)

                self.model.log_event(
                    f"Buyer instruction {self.uniqueID} created child instructions for partial settlement",
                    self.uniqueID, is_transaction=True)

        elif self.role == "seller" and not self.account.checkSufficientSecurities(self.securityType, self.amount):
            available_securities = self.account.checkSufficientSecurities(self.securityType, self.amount)
            if available_securities > 0:
                # Create seller child instructions
                seller_child1 = InstructionAgent(
                    f"{self.uniqueID}_1", self.uniqueID, self.securityType, available_securities, True,
                    "settled", "seller", self.account
                )
                seller_child2 = InstructionAgent(
                    f"{self.uniqueID}_2", self.uniqueID, self.securityType, self.amount - available_securities, True,
                    "pending", "seller", self.account
                )

                # Update seller's account for settled amount
                self.account.updateSecurities(self.securityType, -available_securities)

                # Add child instructions to the model @ruben same here i dont know what this does
                self.model.schedule.add(seller_child1)
                self.model.schedule.add(seller_child2)

                self.model.log_event(
                    f"Seller instruction {self.uniqueID} created child instructions for partial settlement",
                    self.uniqueID, is_transaction=True)


    def settle(self):
        if self.role == "seller":
            if self.account.checkSufficientSecurities(self.securityType, self.amount):
                self.account.updateSecurities(self.securityType, -self.amount)
                self.status = "settled"
            else:
                self.status = "failed"
        elif self.role == "buyer":
            if self.account.checkSufficientCash(self.amount):
                self.account.updateCashBalance(-self.amount)
                self.account.updateSecurities(self.securityType, self.amount)
                self.status = "settled"
            else:
                self.createChildren()
                self.status = "failed"

    def checkSecurities(self) -> bool:
        return self.role == "seller"  # Only sellers check securities

    def checkCash(self) -> bool:
        return self.role == "buyer"  # Only buyers check cash


class TransactionAgent(Agent):
    def __init__(self, TransactionID, model, seller: InstructionAgent, buyer: InstructionAgent, amount, linkcode):
        super().__init__(model)
        self.TransactionID = TransactionID
        self.state = 'Pending'
        self.seller = seller
        self.buyer = buyer
        self.amount = amount
        self.linkcode = linkcode
        self.model.log_event(f"Transaction {TransactionID} created from Account {seller.account.accountID} to Account {buyer.account.accountID} for {amount}", TransactionID, is_transaction=True)

    def validate(self):
        if self.state == 'Pending':
            #.sleep(1) #1-second delay for validation
            self.state = 'Validated'
            self.model.log_event(f"Transaction {self.TransactionID} validated", self.TransactionID, is_transaction=True)

    def match(self):
        self.model.log_event(f"Transaction {self.TransactionID} attempting to find a match", self.TransactionID, is_transaction=True)
        if self.state == 'Validated':
            # Match buyer and seller instructions
            if self.buyer.role == "buyer" and self.seller.role == "seller":
                self.state = 'Matched'
                self.model.log_event(f"Transaction {self.TransactionID} matched with buyer {self.buyer.uniqueID} and seller {self.seller.uniqueID}",self.TransactionID)

    def settle(self):
        self.model.log_event(f"Transaction {self.TransactionID} attempting to settle", self.TransactionID,is_transaction=True)

        if self.state in ['Matched', 'Partially_Settled']:  # Allow reattempts for partial settlements
            # Check if both buyer and seller can settle
            if self.buyer.checkCash() and self.seller.checkSecurities():
                # Deduct cash from buyer and securities from seller
                buyer_settled = self.buyer.account.updateCashBalance(-self.amount)
                seller_settled = self.seller.account.updateSecurities(self.seller.securityType, -self.amount)

                if buyer_settled > 0 and seller_settled > 0:
                    self.state = 'Settled'
                    self.model.log_event(f"Transaction {self.TransactionID} settled fully", self.TransactionID)
                else:
                    self.state = 'Failed'
                    self.model.log_event(f"ERROR: Transaction {self.TransactionID} failed to settle", self.TransactionID, is_transaction=True)
            else:
                # Create child instructions for partial settlement
                self.buyer.createChildren()
                self.seller.createChildren()
                self.state = 'Partially_Settled'
                self.model.log_event(f"Transaction {self.TransactionID} partially settled", self.TransactionID, is_transaction=True)

    def step(self):
        # Removed duplicate Transaction.step method to avoid conflicting transitions
      self.model.log_event(f"Transaction {self.TransactionID} executing step", self.TransactionID, is_transaction=True)

      if self.state == 'Exists':
          self.transition()
      if self.state == 'Pending':
          self.validate()
      if self.state == 'Validated':
          self.match()
      if self.state in ['Matched', 'Partially_Settled']:  # Retry full settlement if previously partial
          self.settle()

class SettlementModel(Model):
    def __init__(self, use_sample_data=False):
        super().__init__()
        self.schedule = []
        self.participants = []
        self.accounts = []
        self.transactions = []
        self.event_log = []
        self.activity_log = []

        if use_sample_data:
            self.generate_sample_data()

    def check_transaction_status(self):
        settled_count = sum(1 for t in self.transactions if t.state == "Settled")
        partially_settled_count = sum(1 for t in self.transactions if t.state == "Partially_Settled")
        pending_count = sum(1 for t in self.transactions if t.state not in ["Settled", "Partially_Settled"])

        print("Simulation Summary:")
        print(f"Total Transactions: {len(self.transactions)}")
        print(f"Fully Settled: {settled_count}")
        print(f"Partially Settled: {partially_settled_count}")
        print(f"Pending/Unsettled: {pending_count}")

        if pending_count > 0:
            print("Unsettled Transactions:")
            for t in self.transactions:
                if t.state not in ["Settled", "Partially_Settled"]:
                    print(f"Transaction {t.TransactionID} - State: {t.state}")

    def log_event(self, message, agent_id, is_transaction=True):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {'Timestamp': timestamp, 'Agent ID': agent_id, 'Event': message}

        if is_transaction:
            if log_entry not in self.event_log:
                print(f"{timestamp} | Agent ID: {log_entry['Agent ID']} | {message}")
                self.event_log.append(log_entry)  # Ensures no duplicates
        else:
            if log_entry not in self.activity_log:
                print(f"{timestamp} | Agent ID: {log_entry['Agent ID']} | {message}")
                  # Ensures no duplicates

        self.activity_log.append(log_entry)




    def save_log(self, filename=None, activity_filename=None):
        if filename is None:
            filename = "event_log.csv"  # Default filename
        df = pd.DataFrame(self.event_log)
        df.to_csv(filename, index=False)
        if activity_filename is None:
            activity_filename = "activity_log.csv"
        df_activity = pd.DataFrame(self.activity_log)
        df_activity.to_csv(activity_filename, index=False)
        print(f"Activity log saved to {activity_filename}")
        print(f"Event Log saved to {filename}")

    def generate_sample_data(self):
        # Create institutions and accounts
        for i in range(5):
            participant = InstitutionAgent(i, self)  # Create institution
            self.participants.append(participant)
            self.schedule.append(participant)

            # Create an account for the institution
            account = AccountAgent(
                i, self, participant,
                cashBalance=random.randint(50, 200),
                creditLimit=random.randint(50, 100))
            participant.add_account(account)
            self.accounts.append(account)
            self.schedule.append(account)

        # Create transactions
        for i in range(20):
            sender = random.choice(self.accounts)
            # Ensure some transactions will partially settle by choosing larger amounts
            amount = random.randint(100, 300) if sender.cashBalance < 100 else random.randint(30, 150)
            receiver = random.choice([acc for acc in self.accounts if acc != sender])

            # Create buyer and seller instructions
            seller_instruction = InstructionAgent(
                f"seller_{i}", "mother", "bond", amount, False, "pending", "seller", sender)
            buyer_instruction = InstructionAgent(
                f"buyer_{i}", "mother", "bond", amount, False, "pending", "buyer", receiver)

            # Create transaction
            transaction = TransactionAgent(
                i, self, seller_instruction, buyer_instruction, amount=amount, linkcode=random.randint(0, 10))
            self.transactions.append(transaction)
            self.schedule.append(transaction)

    def step(self):
        print(f"Running simulation step {self.schedule.count}...")
        for _ in range(len(self.schedule)):
            agent = random.choices(self.schedule, weights=[0.95 if isinstance(a, TransactionAgent) else 0.025 for a in self.schedule])[0]
            if isinstance(agent, TransactionAgent) or isinstance(agent, InstitutionAgent) or isinstance(agent, AccountAgent):
                agent.step()
        print("Step completed.")



if __name__ == "__main__":
    print("Starting simulation...")
    log_path = input("Enter the path to save the log (press Enter for default): ")
    if not log_path.strip():
        log_path = "event_log.csv"
    model = SettlementModel(use_sample_data=True)
    for _ in range(100):
        model.step()
    print("Final Event Log:")
    for event in model.event_log:
        print(event)
    print("Saving final event log...")
    model.check_transaction_status()
    model.save_log(log_path)

