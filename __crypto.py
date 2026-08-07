from Crypto.PublicKey import RSA

def generate_RSA_keys():
    key = RSA.generate(2048)

    private_key = key.export_key()
    with open('private.pem', 'wb') as wb1:
        wb1.write(private_key)

    public_key = key.public_key().export_key()
    with open('public.pem', 'wb') as wb2:
        wb2.write(public_key)



generate_RSA_keys()