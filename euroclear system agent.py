import random
import datetime
import csv
from mesa import Agent, Model
from mesa.time import RandomActivation

# --- Logger Class (unchanged) ---
class Logger:
    def __init__(self):
        self.logs = []
        self.logs.append(["Step", "Timestamp", "Agent", "Event", "TransactionID", "Details"])
    def log(self, step, agent_name, event, tx_id, details=""):
        timestamp = datetime.datetime.now().isoformat()
        self.logs.append([step, timestamp, agent_name, event, tx_id, details])
    def write_csv(self, filename="simulation_log.csv"):
        with open(filename, "w", newline="") as f:
            csv.writer(f).writerows(self.logs)
        print(f"Log written to {filename}")

# --- Messaging Infrastructure (unchanged) ---
class Message:
    def __init__(self, sender, recipient, msg_type, content):
        self.sender = sender
        self.recipient = recipient
        self.msg_type = msg_type
        self.content = content

# --- Account Class (unchanged) ---
class Account:
    def __init__(self, account_type, balance, min_balance):
        self.account_type = account_type
        self.balance = balance
        self.min_balance = min_balance
    def deposit(self, amount):
        self.balance += amount
    def withdraw(self, amount):
        if self.check_balance(amount):
            self.balance -= amount
            return True
        return False
    def check_balance(self, amount):
        return (self.balance - amount) >= self.min_balance

# --- Data Object Classes ---

# Updated SettlementInstruction with sending/receiving institutions and accounts
class SettlementInstruction:
    def __init__(self, instruction_id, transaction_id, instruction_type, security_id,
                 quantity, price, timestamp, sendingInstitution, receivingInstitution,
                 sendingAccount, receivingAccount):
        self.instruction_id = instruction_id
        self.transaction_id = transaction_id
        self.instruction_type = instruction_type  # "Payment" or "Security"
        self.security_id = security_id
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp
        self.sendingInstitution = sendingInstitution
        self.receivingInstitution = receivingInstitution
        self.sendingAccount = sendingAccount
        self.receivingAccount = receivingAccount
        self.status = "New"  # Other statuses: "Canceled", "Settled"
    def validate(self):
        return self.quantity > 0 and self.price > 0
    def cancel(self):
        if self.status not in ["Settled", "Canceled"]:
            self.status = "Canceled"

# New CancelInstruction class
class CancelInstruction:
    def __init__(self, cancel_id, transaction_id, sendingInstitution, timestamp):
        self.cancel_id = cancel_id
        self.transaction_id = transaction_id
        self.sendingInstitution = sendingInstitution
        self.timestamp = timestamp
        self.status = "New"  # Status could be "Processed" once handled

# Other data classes remain unchanged.
class ClearingReport:
    def __init__(self, transaction_id, payer, deliverer, quantity, price, net_amount, risk):
        self.transaction_id = transaction_id
        self.payer = payer
        self.deliverer = deliverer
        self.quantity = quantity
        self.price = price
        self.net_amount = net_amount
        self.risk = risk

class PositioningReport:
    def __init__(self, transaction_id, payer, deliverer, quantity, net_amount, timestamp):
        self.transaction_id = transaction_id
        self.payer = payer
        self.deliverer = deliverer
        self.quantity = quantity
        self.net_amount = net_amount
        self.timestamp = timestamp

class SettlementConfirmation:
    def __init__(self, transaction_id, settlement_status, settlement_date, adjusted_quantity, adjusted_net_amount):
        self.transaction_id = transaction_id
        self.settlement_status = settlement_status  # "Full" or "Partial"
        self.settlement_date = settlement_date
        self.adjusted_quantity = adjusted_quantity
        self.adjusted_net_amount = adjusted_net_amount

# --- Agent Classes with Cancellation Instructions ---

class InstitutionAgent(Agent):
    """
    Objective: Initiate transactions and, if desired, cancel a pending transaction
    by creating a CancelInstruction.
    """
    def __init__(self, unique_id, name, model):
        super().__init__(unique_id, model)
        self.name = name
        self.cash_account = Account("Cash", 1000000, 10000)
        self.security_account = Account("Security", 10000, 100)
        self.initiation_probability = 0.1  # 10% chance per step to initiate a transaction
        self.cancel_probability = 0.05     # 5% chance per step to cancel one pending transaction
        self.inbox = []
    def send_message(self, recipient, msg_type, content):
        msg = Message(self, recipient, msg_type, content)
        recipient.inbox.append(msg)
    def process_messages(self):
        while self.inbox:
            msg = self.inbox.pop(0)
            if msg.msg_type == "validation_result":
                if msg.content["status"] == "Invalid":
                    self.model.logger.log(self.model.current_step, self.name, "ReceivedInvalidation",
                                            msg.content["instruction_id"], "May reinitiate later")
                else:
                    self.model.logger.log(self.model.current_step, self.name, "ReceivedValidation",
                                            msg.content["instruction_id"], "Validated successfully")
            elif msg.msg_type == "settlement_confirmation":
                self.model.logger.log(self.model.current_step, self.name, "SettlementConfirmation",
                                        msg.content["transaction_id"], msg.content["settlement_status"])
    def step(self):
        self.process_messages()
        # With some probability, create a cancellation for a pending transaction
        pending_tx = [instr.transaction_id for instr in self.model.instructions
                      if instr.sendingInstitution == self and instr.status not in ["Canceled", "Settled"]]
        pending_tx += [instr.transaction_id for instr in self.model.validated_instructions
                      if instr.sendingInstitution == self and instr.status not in ["Canceled", "Settled"]]
        pending_tx = list(set(pending_tx))
        if pending_tx and random.random() < self.cancel_probability:
            tx_to_cancel = random.choice(pending_tx)
            cancel_id = f"CANCEL-{tx_to_cancel}"
            cancel_instr = CancelInstruction(cancel_id, tx_to_cancel, self, datetime.datetime.now())
            # Add cancellation instruction to the instructions queue.
            self.model.instructions.append(cancel_instr)
            self.model.logger.log(self.model.current_step, self.name, "IssuedCancellation", tx_to_cancel,
                                    "Cancellation instruction created")
        # With some probability, initiate a new transaction.
        if random.random() < self.initiation_probability:
            counterparties = [inst for inst in self.model.institutions if inst != self]
            if not counterparties:
                return
            counterparty = random.choice(counterparties)
            tx_id = f"TX-{self.model.tx_counter}"
            self.model.tx_counter += 1
            quantity = random.randint(1, 100)
            price = round(random.uniform(10, 100), 2)
            timestamp = datetime.datetime.now()
            # Payment: funds flow from self (sending) to counterparty (receiving)
            payment_instr = SettlementInstruction(
                instruction_id=f"{tx_id}-P",
                transaction_id=tx_id,
                instruction_type="Payment",
                security_id="SEC-XYZ",
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                sendingInstitution=self,
                receivingInstitution=counterparty,
                sendingAccount=self.cash_account,
                receivingAccount=counterparty.cash_account
            )
            # Security: securities flow from counterparty (sending) to self (receiving)
            security_instr = SettlementInstruction(
                instruction_id=f"{tx_id}-S",
                transaction_id=tx_id,
                instruction_type="Security",
                security_id="SEC-XYZ",
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                sendingInstitution=counterparty,
                receivingInstitution=self,
                sendingAccount=counterparty.security_account,
                receivingAccount=self.security_account
            )
            self.model.instructions.extend([payment_instr, security_instr])
            self.model.logger.log(self.model.current_step, self.name, "InitiatedTransaction", tx_id,
                                    f"Qty: {quantity}, Price: {price} with {counterparty.name}")

class ValidationAgent(Agent):
    """
    Objective: Validate instructions and process cancellation instructions.
    """
    def __init__(self, unique_id, name, model):
        super().__init__(unique_id, model)
        self.name = name
        self.inbox = []
    def send_message(self, recipient, msg_type, content):
        msg = Message(self, recipient, msg_type, content)
        recipient.inbox.append(msg)
    def process_cancel_instruction(self, cancel_instr):
        tx = cancel_instr.transaction_id
        canceled_count = 0
        # Cancel in instructions
        for instr in self.model.instructions:
            if not hasattr(instr, "cancel_id") and instr.transaction_id == tx and instr.status not in ["Canceled", "Settled"]:
                instr.cancel()
                canceled_count += 1
        # Cancel in validated_instructions
        for instr in self.model.validated_instructions:
            if instr.transaction_id == tx and instr.status not in ["Canceled", "Settled"]:
                instr.cancel()
                canceled_count += 1
        # Cancel in matched_pairs
        if tx in self.model.matched_pairs:
            pair = self.model.matched_pairs[tx]
            for key in pair:
                if pair[key] is not None and pair[key].status not in ["Canceled", "Settled"]:
                    pair[key].cancel()
                    canceled_count += 1
            del self.model.matched_pairs[tx]
        self.model.logger.log(self.model.current_step, self.name, "ProcessedCancellation", tx, f"Canceled {canceled_count} instructions")
    def step(self):
        # Process cancellation instructions if any are in the instructions queue
        remaining_instructions = []
        for instr in self.model.instructions:
            if isinstance(instr, CancelInstruction):
                self.process_cancel_instruction(instr)
            else:
                remaining_instructions.append(instr)
        self.model.instructions = remaining_instructions

        # Now process regular settlement instructions
        if self.model.instructions:
            new_instr = self.model.instructions[:]
            self.model.instructions = []
            for instr in new_instr:
                if isinstance(instr, SettlementInstruction):
                    if instr.status == "Canceled":
                        self.model.logger.log(self.model.current_step, self.name, "SkippedCanceledInstruction", instr.instruction_id, "")
                        continue
                    if instr.validate():
                        self.model.validated_instructions.append(instr)
                        self.send_message(instr.sendingInstitution, "validation_result", {"instruction_id": instr.instruction_id, "status": "Valid"})
                        self.model.logger.log(self.model.current_step, self.name, "ValidatedInstruction", instr.instruction_id, "Valid")
                    else:
                        self.send_message(instr.sendingInstitution, "validation_result", {"instruction_id": instr.instruction_id, "status": "Invalid"})
                        self.model.logger.log(self.model.current_step, self.name, "ValidatedInstruction", instr.instruction_id, "Invalid")

class MatchingAgent(Agent):
    """
    Objective: Match Payment and Security instructions.
    """
    def __init__(self, unique_id, name, model):
        super().__init__(unique_id, model)
        self.name = name
        self.inbox = []
    def step(self):
        for instr in self.model.validated_instructions:
            if instr.status == "Canceled":
                continue
            tx = instr.transaction_id
            if tx not in self.model.matched_pairs:
                self.model.matched_pairs[tx] = {"Payment": None, "Security": None}
            self.model.matched_pairs[tx][instr.instruction_type] = instr
        self.model.validated_instructions = []
        complete = {tx: pair for tx, pair in self.model.matched_pairs.items()
                    if pair["Payment"] and pair["Security"] and
                       pair["Payment"].status != "Canceled" and pair["Security"].status != "Canceled"}
        self.model.matched_pairs = complete
        self.model.logger.log(self.model.current_step, self.name, "MatchedTransactions", "", f"{len(complete)} complete pairs")

class ClearingAgent(Agent):
    """
    Objective: Compute net amounts and risks from matched transactions.
    """
    def __init__(self, unique_id, name, model):
        super().__init__(unique_id, model)
        self.name = name
        self.inbox = []
    def step(self):
        for tx, pair in list(self.model.matched_pairs.items()):
            if pair["Payment"].status == "Canceled" or pair["Security"].status == "Canceled":
                self.model.logger.log(self.model.current_step, self.name, "CanceledPair", tx, "Skipping canceled transaction")
                del self.model.matched_pairs[tx]
                continue
            payment = pair["Payment"]
            net_amount = payment.quantity * payment.price
            risk = net_amount * 0.05
            report = ClearingReport(tx, payment.sendingInstitution, pair["Security"].sendingInstitution,
                                      payment.quantity, payment.price, net_amount, risk)
            self.model.clearing_reports.append(report)
            self.model.total_possible_net += net_amount
            self.model.logger.log(self.model.current_step, self.name, "ClearingReport", tx, f"Net: {net_amount}, Risk: {risk}")
            del self.model.matched_pairs[tx]
        self.model.logger.log(self.model.current_step, self.name, "ClearingComplete", "", f"{len(self.model.clearing_reports)} reports generated")

class PositioningAgent(Agent):
    """
    Objective: Generate positioning reports.
    """
    def __init__(self, unique_id, name, model):
        super().__init__(unique_id, model)
        self.name = name
        self.inbox = []
    def step(self):
        for report in self.model.clearing_reports:
            pos_report = PositioningReport(report.transaction_id, report.payer, report.deliverer,
                                           report.quantity, report.net_amount, datetime.datetime.now())
            self.model.positioning_reports.append(pos_report)
            self.model.logger.log(self.model.current_step, self.name, "PositioningReport", report.transaction_id, f"Qty: {report.quantity}, Net: {report.net_amount}")
        count = len(self.model.clearing_reports)
        self.model.clearing_reports = []
        self.model.logger.log(self.model.current_step, self.name, "PositioningComplete", "", f"{count} reports generated")

class SettlementAgent(Agent):
    """
    Objective: Execute settlements ensuring that accounts remain above minimum balances.
    """
    def __init__(self, unique_id, name, model):
        super().__init__(unique_id, model)
        self.name = name
        self.inbox = []
    def send_message(self, recipient, msg_type, content):
        msg = Message(self, recipient, msg_type, content)
        recipient.inbox.append(msg)
    def step(self):
        for report in self.model.positioning_reports:
            payer = report.payer
            deliverer = report.deliverer
            net_amount = report.net_amount
            quantity = report.quantity
            price = net_amount / quantity if quantity else 0
            adjusted = False
            if not payer.cash_account.check_balance(net_amount):
                allowed_cash = payer.cash_account.balance - payer.cash_account.min_balance
                if allowed_cash <= 0:
                    self.model.logger.log(self.model.current_step, self.name, "SettlementSkipped", report.transaction_id, f"{payer.name} insufficient cash")
                    continue
                net_amount = allowed_cash
                quantity = int(net_amount / price)
                adjusted = True
            if not deliverer.security_account.check_balance(quantity):
                allowed_qty = deliverer.security_account.balance - deliverer.security_account.min_balance
                if allowed_qty <= 0:
                    self.model.logger.log(self.model.current_step, self.name, "SettlementSkipped", report.transaction_id, f"{deliverer.name} insufficient securities")
                    continue
                quantity = allowed_qty
                net_amount = quantity * price
                adjusted = True
            if payer.cash_account.withdraw(net_amount):
                payer.security_account.deposit(quantity)
            else:
                self.model.logger.log(self.model.current_step, self.name, "SettlementFailed", report.transaction_id, f"Unable to withdraw from {payer.name}")
                continue
            deliverer.cash_account.deposit(net_amount)
            if not deliverer.security_account.withdraw(quantity):
                self.model.logger.log(self.model.current_step, self.name, "SettlementFailed", report.transaction_id, f"Unable to withdraw securities from {deliverer.name}")
                continue
            settlement_status = "Partial" if adjusted else "Full"
            confirmation = SettlementConfirmation(report.transaction_id, settlement_status, datetime.datetime.now(), quantity, net_amount)
            self.model.settlement_confirmations.append(confirmation)
            self.send_message(payer, "settlement_confirmation", {"transaction_id": report.transaction_id, "settlement_status": settlement_status})
            self.send_message(deliverer, "settlement_confirmation", {"transaction_id": report.transaction_id, "settlement_status": settlement_status})
            self.model.logger.log(self.model.current_step, self.name, "SettledTransaction", report.transaction_id, f"{settlement_status}: Qty {quantity}, Net {net_amount}")
        count = len(self.model.positioning_reports)
        self.model.positioning_reports = []

# --- The Model ---
class SettlementModel(Model):
    def __init__(self, total_steps=50):
        self.schedule = RandomActivation(self)
        self.current_step = 0
        self.total_steps = total_steps
        self.logger = Logger()
        self.institutions = []
        for i in range(4):
            agent = InstitutionAgent(i+1, f"Institution_{i+1}", self)
            self.institutions.append(agent)
            self.schedule.add(agent)
        self.validation_agent = ValidationAgent(101, "ValidationAgent", self)
        self.matching_agent = MatchingAgent(102, "MatchingAgent", self)
        self.clearing_agent = ClearingAgent(103, "ClearingAgent", self)
        self.positioning_agent = PositioningAgent(104, "PositioningAgent", self)
        self.settlement_agent = SettlementAgent(105, "SettlementAgent", self)
        self.schedule.add(self.validation_agent)
        self.schedule.add(self.matching_agent)
        self.schedule.add(self.clearing_agent)
        self.schedule.add(self.positioning_agent)
        self.schedule.add(self.settlement_agent)
        self.instructions = []
        self.validated_instructions = []
        self.matched_pairs = {}
        self.clearing_reports = []
        self.positioning_reports = []
        self.settlement_confirmations = []
        self.tx_counter = 1
        self.total_possible_net = 0

    def calculate_settlement_efficiency(self):
        total_settled = sum(conf.adjusted_net_amount for conf in self.settlement_confirmations)
        if self.total_possible_net > 0:
            efficiency = (total_settled / self.total_possible_net) * 100
        else:
            efficiency = 0
        return efficiency

    def step(self):
        self.current_step += 1
        self.logger.log(self.current_step, "Model", "StepStart", "", f"Step {self.current_step} begins")
        self.schedule.step()

if __name__ == "__main__":
    model = SettlementModel(total_steps=100)
    for _ in range(model.total_steps):
        model.step()
    efficiency = model.calculate_settlement_efficiency()
    model.logger.log(model.current_step, "Model", "SettlementEfficiency", "", f"Efficiency: {efficiency:.2f}%")
    model.logger.write_csv("simulation_log.csv")


