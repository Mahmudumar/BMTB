from scripts.password_manager import SimpleCipher

s = SimpleCipher()
print(s.pass_hash("123"))

# print(bool(str(None).strip()))
a = ""
b = "s"
c = "h"
print(None or a or b or c)