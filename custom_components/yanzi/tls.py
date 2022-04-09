import json
import logging
import ssl
import tempfile
import aiohttp.client
from time import time
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from cryptography.x509.oid import NameOID


from custom_components.yanzi.const import COP_ROOT, COP_SIGN_URL
from custom_components.yanzi.errors import InvalidAuth

_LOGGER = logging.getLogger(__name__)


async def get_ssl_context(pk: str, chain: str):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(None, None, COP_ROOT)
    with tempfile.TemporaryFile() as pkfile:
        with tempfile.TemporaryFile() as chainfile:
            pkfile.write(pk)
            chainfile.write(chain)
            ctx.load_cert_chain(pkfile, chainfile)

    return ctx


async def get_certificate(username: str, password: str):
    private_key, csr = get_csr(username)
    data = {
        "did": f"hass-{username}-{int(time())}",
        "yanziId": username,
        "password": password,
        "csr": csr.decode()
    }

    async with aiohttp.client.request("POST", COP_SIGN_URL, json=data) as res:
        data = await res.json()
        if data["status"] != "ACCEPTED":
            _LOGGER.error("Failed to generate certificate: %s",
                          json.dumps(data))
            raise InvalidAuth

        return private_key, data["certificateChain"]


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
        NoEncryption()
    )

    csr = request.public_bytes(Encoding.PEM)

    return private_key, csr
