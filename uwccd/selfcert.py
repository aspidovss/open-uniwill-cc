"""A self-signed TLS certificate for the external API over HTTPS (1.8.2.0), without third-party packages.

Python's ssl module can serve HTTPS but cannot make a certificate, and the Windows build does not ship `cryptography`
or `openssl`. A server certificate is small enough to build by hand: an RSA key (Miller-Rabin primes), an X.509 v3
certificate in DER (subjectAltName with localhost, the computer name and the given IP addresses), signed with
SHA-256 / PKCS#1 v1.5. Clients check it by its SHA-256 fingerprint, shown in Settings -> API, or trust cert.pem.

    make(cert_path, key_path, names=("localhost",), ips=("192.168.1.5",)) -> fingerprint "AB:CD:..."
"""
import base64
import datetime
import hashlib
import ipaddress
import secrets

E = 65537
_SMALL_PRIMES = [p for p in range(3, 2000, 2) if all(p % d for d in range(3, int(p ** .5) + 1, 2))]


# -- RSA -------------------------------------------------------------------------------------------
def _probable_prime(n, rounds=40):
    if any(n % p == 0 for p in _SMALL_PRIMES):
        return n in _SMALL_PRIMES
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    while True:
        c = secrets.randbits(bits) | (3 << (bits - 2)) | 1        # top two bits set: n has exactly 2*bits bits
        if (c - 1) % E and _probable_prime(c):
            return c


def rsa_key(bits=2048):
    while True:
        p, q = _prime(bits // 2), _prime(bits // 2)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        d = pow(E, -1, phi)
        if p < q:
            p, q = q, p
        return {"n": p * q, "e": E, "d": d, "p": p, "q": q,
                "dp": d % (p - 1), "dq": d % (q - 1), "qi": pow(q, -1, p)}


# -- DER -------------------------------------------------------------------------------------------
def _len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag, body):
    return bytes([tag]) + _len(len(body)) + body


def _int(v):
    b = v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big")        # one spare bit keeps it positive
    return _tlv(0x02, b)


def _seq(*items):
    return _tlv(0x30, b"".join(items))


def _oid(dotted):
    parts = [int(x) for x in dotted.split(".")]
    out = bytearray([40 * parts[0] + parts[1]])
    for v in parts[2:]:
        chunk = [v & 0x7F]
        v >>= 7
        while v:
            chunk.append(0x80 | (v & 0x7F))
            v >>= 7
        out += bytes(reversed(chunk))
    return _tlv(0x06, bytes(out))


NULL = b"\x05\x00"
RSA_ENC = _seq(_oid("1.2.840.113549.1.1.1"), NULL)
SHA256_RSA = _seq(_oid("1.2.840.113549.1.1.11"), NULL)
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _name(cn):
    return _seq(_tlv(0x31, _seq(_oid("2.5.4.3"), _tlv(0x0C, cn.encode()))))


def _time(dt):
    if dt.year < 2050:
        return _tlv(0x17, dt.strftime("%y%m%d%H%M%SZ").encode())
    return _tlv(0x18, dt.strftime("%Y%m%d%H%M%SZ").encode())


def _san(names, ips):
    gn = b"".join(_tlv(0x82, n.encode("ascii")) for n in names)
    gn += b"".join(_tlv(0x87, ipaddress.ip_address(i).packed) for i in ips)
    return _seq(_oid("2.5.29.17"), _tlv(0x04, _seq(gn)))


def _sign(k, data):
    digest = SHA256_DIGEST_INFO + hashlib.sha256(data).digest()
    size = (k["n"].bit_length() + 7) // 8
    em = b"\x00\x01" + b"\xff" * (size - len(digest) - 3) + b"\x00" + digest
    m = int.from_bytes(em, "big")
    # CRT: four times faster than pow(m, d, n)
    s1, s2 = pow(m, k["dp"], k["p"]), pow(m, k["dq"], k["q"])
    s = s2 + k["q"] * ((k["qi"] * (s1 - s2)) % k["p"])
    return s.to_bytes(size, "big")


def certificate(k, cn="open-uniwill-cc", names=("localhost",), ips=(), days=3650):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    spki = _seq(RSA_ENC, _tlv(0x03, b"\x00" + _seq(_int(k["n"]), _int(k["e"]))))
    names = [n for n in dict.fromkeys(names) if n and all(ord(c) < 128 for c in n)]
    ips = list(dict.fromkeys(str(i) for i in ips))
    tbs = _seq(
        _tlv(0xA0, _int(2)),                                         # v3
        _int(secrets.randbits(63) | 1),
        SHA256_RSA,
        _name(cn),
        _seq(_time(now - datetime.timedelta(days=1)), _time(now + datetime.timedelta(days=days))),
        _name(cn),
        spki,
        _tlv(0xA3, _seq(_san(names, ips))),
    )
    return _seq(tbs, SHA256_RSA, _tlv(0x03, b"\x00" + _sign(k, tbs)))


def _pem(kind, der):
    b = base64.b64encode(der).decode()
    return f"-----BEGIN {kind}-----\n" + "\n".join(b[i:i + 64] for i in range(0, len(b), 64)) + f"\n-----END {kind}-----\n"


def key_der(k):
    return _seq(_int(0), *(_int(k[x]) for x in ("n", "e", "d", "p", "q", "dp", "dq", "qi")))


def fingerprint(der):
    return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())


def pem_fingerprint(pem_text):
    body = "".join(x for x in pem_text.splitlines() if x and not x.startswith("-----"))
    return fingerprint(base64.b64decode(body))


def make(cert_path, key_path, names=("localhost",), ips=(), bits=2048):
    """Write cert.pem and key.pem (PKCS#1); -> the SHA-256 fingerprint of the certificate."""
    k = rsa_key(bits)
    der = certificate(k, names=names, ips=ips)
    with open(key_path, "w", encoding="ascii") as f:
        f.write(_pem("RSA PRIVATE KEY", key_der(k)))
    with open(cert_path, "w", encoding="ascii") as f:
        f.write(_pem("CERTIFICATE", der))
    return fingerprint(der)
