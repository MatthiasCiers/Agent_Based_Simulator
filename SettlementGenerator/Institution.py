class Institution:
    def __init__(self, institution_id, name):
        self.institution_id = institution_id
        self.name = name
        # Each institution now has separate lists for "from" and "to" accounts.
        self.accounts= []


    def add_account(self, account):
        self.accounts.append(account)


    def __str__(self):
        return (f"Institution({self.institution_id}, {self.name}, "
                f"Accounts: {len(self.accounts)}")
#new