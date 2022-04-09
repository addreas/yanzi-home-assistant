from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from cryptography.x509.oid import NameOID


def get_csr(username: str):
    pk = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    request = x509.CertificateSigningRequestBuilder(
    ).subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, username)
    ])).add_extension(
        x509.BasicConstraints(ca=False, path_length=None), critical=True
    ).sign(pk, hashes.SHA256())

    private_key = pk.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        NoEncryption
    )

    csr = request.public_bytes(Encoding.PEM)

    return private_key, csr
