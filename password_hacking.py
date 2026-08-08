import base64

from scripts.password_manager import Cryptography

a = Cryptography()

DEK = a.generate_new_DEK()

# NOTE: store this
salt = a.generate_salt()
salt_stored = base64.urlsafe_b64encode(salt)

password = "12345"

KEK = a.derive_KEK(password, salt)

# NOTE: store this
encDEK = a.encrypt_DEK(KEK, DEK)

print(f"Data Encryption Key: {DEK}")
print(f"Master Password: {password}")
print(f"Salt: {salt}")
print(f"Stored Salt:{salt_stored}")
# what is derived from pass and salt used to encrypt DEK
print(f"Key Encryption Key: {KEK}")


note = "Hello there"
print()
print(f"Note: {note}")

# NOTE: store this
encrypted_note = a.encrypt_note(DEK, note)


# print(f"Encrypting note to: {encrypted_note}")
print("Encrypted note")
print()


# print(f"Final Encrypted DEK : {encDEK}")
print("Encrypted DEK: Safe to store encDEK")


# decrypting the encDEK

print("DECRYPTION")
print(f"Using stored salt: {salt_stored}")
got_salt = base64.urlsafe_b64decode(salt_stored)
print(f"Back to original: {got_salt}")

KEK2 = a.derive_KEK(password, got_salt)
print(f"Derived KEK from stored salt: {KEK2}")
decrypted_DEK = a.decrypt_DEK(KEK2, encDEK)

print(f"Decrypted DEK: {decrypted_DEK}")
print()
print(f"Encrypted Note: {encrypted_note}")
dec_note = a.decrypt_note(decrypted_DEK, encrypted_note)
print(f"Decrypting note back to: {dec_note}")
print()
