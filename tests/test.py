from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

print("admin:", pwd.hash("admin123")) # admin hashed_password
print("user:", pwd.hash("user123")) # user hashed_password
# prints hashed passwords to be used in USERS_DB: 