from random import randint

def generate_otp():
    return str(randint(100000, 999999))
