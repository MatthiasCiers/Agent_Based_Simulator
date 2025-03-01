class Account:
    def __init__(self, accountID, institutionID, securities, cashBalance, creditLimit):
        # Extended attributes
        self.accountID = accountID
        self.institutionID = institutionID
        self.state = 'Exists'
        self.cashBalance = cashBalance
        self.securities = securities  # Dictionary mapping security type to amount (e.g. {"Bond-A": 10000})
        self.creditLimit = creditLimit


    def __str__(self):
        return (f"Account({self.accountID}, Institution: {self.institutionID}, "
                f"State: {self.state}, Cash Balance: {self.cashBalance}, Securities: {self.securities}, "
                f"Credit Limit: {self.creditLimit}")