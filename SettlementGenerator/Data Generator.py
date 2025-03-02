import csv
import uuid
import random
from datetime import datetime, timedelta
import Account
import Institution
import Transaction
import Instruction



#helper functions
def generate_short_id(length=6):
    """Generate a short hex-based ID (default 6 characters)."""
    return uuid.uuid4().hex[:length].upper()

#helper function
def generate_iban():
    """Generate a simple IBAN-like string.
    Example: 'DE45' + 16 digits.
    """
    country_code = random.choice(["DE", "FR", "NL", "GB"])
    check_digits = str(random.randint(10, 99))
    bban = ''.join(random.choices("0123456789", k=5))
    return f"{country_code}{check_digits}{bban}"

class SettlementDataGenerator:
    NUM_INSTITUTIONS = 8
    NUM_TRANSACTIONS = 1000   # For sample output; change to 5000 as needed.
    MIN_TOTAL_ACCOUNTS = 6
    MAX_TOTAL_ACCOUNTS = 10
    SIMULATION_DURATION_DAYS = 10

    def __init__(self):
        self.simulation_start = datetime.now()
        self.institutions = []  # List of Institution objects
        self.accounts = []      # NEW: Master list of all extended Account objects
        self.transactions = []  # List of Transaction objects
        self.bond_types = ["Bond-A", "Bond-B", "Bond-C", "Bond-D"]

    def generate_institutions(self):
        for i in range(1, SettlementDataGenerator.NUM_INSTITUTIONS + 1):
            inst_id = f"INST-{i}"
            institution = Institution.Institution(inst_id, f"Institution {i}")
            total_accounts = random.randint(SettlementDataGenerator.MIN_TOTAL_ACCOUNTS,
                                            SettlementDataGenerator.MAX_TOTAL_ACCOUNTS)


           #create accounts
            for _ in range(total_accounts):
                accountID = generate_iban()
                # NEW: Random securities assignment (50% chance)
                if random.random() < 0.5:
                    sec_type = random.choice(self.bond_types)
                    securities = {sec_type: random.randint(10000, 50000)}
                else:
                    securities = {}
                cashBalance = round(random.uniform(5000, 200000), 2)
                creditLimit = round(random.uniform(100000, 500000), 2)
                account = Account.Account(accountID, inst_id, securities, cashBalance, creditLimit)
                institution.add_account(account)
                self.accounts.append(account)




            self.institutions.append(institution)

    def random_timestamp(self):
        simulation_end = self.simulation_start + timedelta(days=SettlementDataGenerator.SIMULATION_DURATION_DAYS)
        delta = simulation_end - self.simulation_start
        random_seconds = random.uniform(0, delta.total_seconds())
        random_time = self.simulation_start + timedelta(seconds=random_seconds)
        return random_time.isoformat(sep='T', timespec='seconds')

    def generate_transactions(self):
        for _ in range(SettlementDataGenerator.NUM_TRANSACTIONS):
            seller_inst = random.choice(self.institutions)
            buyer_inst = random.choice(self.institutions)
            while buyer_inst == seller_inst:
                buyer_inst = random.choice(self.institutions)


            # For bond leg, swap: buyer's "from" and seller's "to" accounts.
            buyer_account = random.choice(buyer_inst.accounts)
            seller_account = random.choice(seller_inst.accounts)
            amount = round(random.uniform(1000, 100000), 2)
            link_code = "LINK-" + generate_short_id(6)

            # Generate two independent timestamps; ensure cash < bond.
            t1 = self.random_timestamp()
            t2 = self.random_timestamp()
            if t1 >= t2:
                cash_timestamp, bond_timestamp = t2, t1
            else:
                cash_timestamp, bond_timestamp = t1, t2
            if cash_timestamp == bond_timestamp:
                bond_timestamp = (datetime.fromisoformat(cash_timestamp) + timedelta(seconds=1)).isoformat(sep='T', timespec='seconds')

            cash_instruction = Instruction.Instruction(
                unique_id=generate_short_id(6),
                mother_id="DUMMY",
                security_type="Cash",
                amount=amount,
                is_child=False,
                status="Exists",
                role="Cash",
                link_code=link_code,
                from_account=buyer_account,
                to_account=seller_account,
                timestamp=cash_timestamp
            )
            bond_security = random.choice(self.bond_types)
            bond_instruction = Instruction.Instruction(
                unique_id=generate_short_id(6),
                mother_id="DUMMY",
                security_type=bond_security,
                amount=amount,
                is_child=False,
                status="Exists",
                role="Bond",
                link_code=link_code,
                from_account=seller_account,
                to_account=buyer_account,
                timestamp=bond_timestamp
            )
            transaction_id = "TX-" + generate_short_id(6)
            transaction = Transaction.Transaction(transaction_id, cash_instruction, bond_instruction)
            self.transactions.append(transaction)

    def write_instructions_to_csv(self, filename):
        # Collect and globally sort all instructions by timestamp.
        instructions = []
        for tx in self.transactions:
            instructions.append((tx.transaction_id, tx.cash_instruction))
            instructions.append((tx.transaction_id, tx.bond_instruction))
        instructions.sort(key=lambda x: x[1].timestamp)
        with open(filename, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "transactionID", "instructionUniqueID", "motherID",
                "sellerInstitutionID", "buyerInstitutionID",
                "fromAccountID", "toAccountID", "securityType",
                "amount", "isChild", "status", "role", "linkCode", "timestamp"
            ])
            for tx_id, instr in instructions:
                if instr.role == "Cash":
                    seller_inst_id = instr.to_account.institutionID
                    buyer_inst_id = instr.from_account.institutionID
                else:  # Bond leg: swapped
                    seller_inst_id = instr.from_account.institutionID
                    buyer_inst_id = instr.to_account.institutionID
                writer.writerow([
                    tx_id,
                    instr.unique_id,
                    instr.mother_id,
                    seller_inst_id,
                    buyer_inst_id,
                    instr.from_account.accountID,
                    instr.to_account.accountID,
                    instr.security_type,
                    instr.amount,
                    instr.is_child,
                    instr.status,
                    instr.role,
                    instr.link_code,
                    instr.timestamp
                ])

    # ================================
    # NEW: Write Institutions to CSV
    # ================================
    def write_institutions_to_csv(self, filename):
        with open(filename, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["institutionID", "name", "Accounts"])
            for inst in self.institutions:
                accounts_str = ";".join([acc.accountID for acc in inst.accounts])
                writer.writerow([inst.institution_id, inst.name, accounts_str])




    # ================================
    # NEW: Write Accounts to CSV
    # ================================
    def write_accounts_to_csv(self, filename):
        with open(filename, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["accountID", "institutionID", "state", "cashBalance", "securities", "creditLimit"])
            for acc in self.accounts:
                # Convert the securities dictionary to a string.
                securities_str = ";".join([f"{k}:{v}" for k, v in acc.securities.items()])
                writer.writerow([acc.accountID, acc.institutionID, acc.state, acc.cashBalance, securities_str, acc.creditLimit])

    def run(self):
        print("Generating institutions and accounts...")
        self.generate_institutions()
        print("Generating transactions...")
        self.generate_transactions()
        print("Writing instructions to CSV file: settlement_instructions.csv")
        self.write_instructions_to_csv("settlement_instructions.csv")
        print("Writing institutions to CSV file: institutions.csv")
        self.write_institutions_to_csv("institutions.csv")
        print("Writing accounts to CSV file: accounts.csv")
        self.write_accounts_to_csv("accounts.csv")
        print(f"Done! Generated {SettlementDataGenerator.NUM_TRANSACTIONS} transactions, "
              f"{len(self.institutions)} institutions, and {len(self.accounts)} accounts.")

if __name__ == "__main__":
    generator = SettlementDataGenerator()
    generator.run()
