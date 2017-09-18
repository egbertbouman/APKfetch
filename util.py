import base64
import hashlib

from struct import unpack_from

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

GOOGLE_PUBLIC_KEY = 'AAAAgMom/1a/v0lblO2Ubrt60J2gcuXSljGFQXgcyZWveWLEwo6prwgi3iJIZdodyhKZQrNWp5nKJ3srRXcUW+F1BD3baEVGcmEgqaLZUNBjm057pKRI16kB0YppeGx5qIQ5QjKzsR8ETQbKLNWgRY0QRNVz34kMJR3P/LgHax/6rmf5AAAAAwEAAQ=='


def encrypt(username, password):
    public_key = base64.b64decode(GOOGLE_PUBLIC_KEY)

    modulus_length = read_length(public_key, 0)
    modulus_data = public_key[4:4+modulus_length]
    modulus = long(modulus_data.encode('hex'), 16)

    exponent_length = read_length(public_key, 4+modulus_length)
    exponent_data = public_key[8+modulus_length:8+modulus_length+exponent_length]
    exponent = long(exponent_data.encode('hex'), 16)

    signature = '\x00' + hashlib.sha1(public_key).digest()[:4]

    key = RSA.construct((modulus, exponent))
    cipher = PKCS1_OAEP.new(key)
    plaintext = username + '\x00' + password
    ciphertext = cipher.encrypt(plaintext)

    result = signature + ciphertext
    return base64.urlsafe_b64encode(result)
	
def read_length(bin, offset):
    return (0xff & ord(bin[offset])) << 24 | \
           (0xff & ord(bin[offset+1])) << 16 | \
		   (0xff & ord(bin[offset+2])) << 8 | \
		   (0xff & ord(bin[offset+3])) << 0
