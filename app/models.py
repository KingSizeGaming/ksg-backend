from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

    def get_id(self):
        return self.id




