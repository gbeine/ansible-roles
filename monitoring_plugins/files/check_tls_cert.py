#!/usr/bin/env python3
"""
check_tls_cert.py - Nagios/Icinga Plugin zur Prüfung des Ablaufdatums von
TLS/SSL-Zertifikaten für beliebige TCP-basierte Protokolle (HTTPS, SMTP,
IMAP, POP3, LDAP, FTP, XMPP, MySQL, PostgreSQL, NNTP, Sieve, MQTT, ...).

Nutzt das systemeigene `openssl`-Binary (s_client) fuer Verbindungsaufbau,
STARTTLS-Negotiation und Zertifikatsabruf. Dadurch sind keine zusaetzlichen
Python-Abhaengigkeiten (z.B. `cryptography`) auf dem Monitoring-Host
erforderlich.

Exit-Codes gemaess Nagios/Icinga Plugin API:
  0 OK, 1 WARNING, 2 CRITICAL, 3 UNKNOWN
"""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

NAGIOS_OK = 0
NAGIOS_WARNING = 1
NAGIOS_CRITICAL = 2
NAGIOS_UNKNOWN = 3

STATUS_NAMES = {
    NAGIOS_OK: "OK",
    NAGIOS_WARNING: "WARNING",
    NAGIOS_CRITICAL: "CRITICAL",
    NAGIOS_UNKNOWN: "UNKNOWN",
}

# Protokolle, die openssl s_client per "-starttls <proto>" unterstuetzt.
# Welche davon auf einem konkreten System verfuegbar sind, zeigt:
#   openssl s_client -starttls bogus 2>&1 | grep -A1 'unknown protocol'
STARTTLS_PROTOCOLS = [
    "smtp", "pop3", "imap", "ftp", "xmpp", "xmpp-server",
    "irc", "ldap", "mysql", "postgres", "nntp", "sieve", "lmtp",
]

CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)
VERIFY_RE = re.compile(r"Verify return code:\s*(\d+)\s*\(([^)]*)\)")
ENDDATE_RE = re.compile(r"notAfter=(.+)")
SUBJECT_RE = re.compile(r"^subject=\s*(.+)$", re.MULTILINE)
ISSUER_RE = re.compile(r"^issuer=\s*(.+)$", re.MULTILINE)


def die(status, message):
    print(f"{STATUS_NAMES[status]}: {message}")
    sys.exit(status)


def parse_args():
    p = argparse.ArgumentParser(
        description="Prueft das Ablaufdatum eines TLS/SSL-Zertifikats fuer "
                     "beliebige TCP-Protokolle (mit oder ohne STARTTLS)."
    )
    p.add_argument("-H", "--host", required=True,
                    help="Hostname oder IP-Adresse des Zielsystems")
    p.add_argument("-p", "--port", required=True, type=int,
                    help="TCP-Port")
    p.add_argument("-t", "--starttls", choices=STARTTLS_PROTOCOLS, default=None,
                    help="STARTTLS fuer das angegebene Protokoll aushandeln, "
                         "bevor der TLS-Handshake beginnt. Weglassen bei "
                         "Protokollen mit direktem TLS (HTTPS, IMAPS, POP3S, "
                         "LDAPS, FTPS-implicit, MQTT-TLS, ...).")
    p.add_argument("-w", "--warning", type=int, default=30,
                    help="Warning, wenn weniger als N Tage verbleiben (Default: 30)")
    p.add_argument("-c", "--critical", type=int, default=15,
                    help="Critical, wenn weniger als N Tage verbleiben (Default: 15)")
    p.add_argument("--cafile", help="Pfad zu einer CA-Bundle-Datei (PEM), gegen "
                                     "die die Zertifikatskette validiert wird")
    p.add_argument("--capath", help="Pfad zu einem OpenSSL-Hash-Verzeichnis mit "
                                     "CA-Zertifikaten")
    p.add_argument("--no-verify", action="store_true",
                    help="Nur Ablaufdatum pruefen, Chain-Validierungsfehler "
                         "ignorieren (auch wenn --cafile/--capath gesetzt ist)")
    p.add_argument("--sni", help="Servername fuer SNI (Default: --host)")
    p.add_argument("--timeout", type=int, default=10,
                    help="Timeout in Sekunden fuer Verbindungsaufbau/Handshake "
                         "(Default: 10)")
    p.add_argument("-4", dest="force_ipv4", action="store_true", help="IPv4 erzwingen")
    p.add_argument("-6", dest="force_ipv6", action="store_true", help="IPv6 erzwingen")
    return p.parse_args()


def find_openssl():
    openssl = shutil.which("openssl")
    if not openssl:
        die(NAGIOS_UNKNOWN, "openssl Binary nicht im PATH gefunden")
    return openssl


def build_s_client_command(openssl, args):
    cmd = [
        openssl, "s_client",
        "-connect", f"{args.host}:{args.port}",
        "-servername", args.sni or args.host,
    ]
    if args.starttls:
        cmd += ["-starttls", args.starttls]
    if args.cafile:
        cmd += ["-CAfile", args.cafile]
    if args.capath:
        cmd += ["-CApath", args.capath]
    if args.force_ipv4:
        cmd.append("-4")
    if args.force_ipv6:
        cmd.append("-6")
    return cmd


def run(cmd, timeout, input_data=b""):
    try:
        proc = subprocess.run(
            cmd,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        die(NAGIOS_UNKNOWN, f"Timeout nach {timeout}s bei Verbindung/TLS-Handshake")
    except FileNotFoundError:
        die(NAGIOS_UNKNOWN, "openssl Binary konnte nicht ausgefuehrt werden")
    return proc.stdout.decode("utf-8", errors="replace")


def extract_certificate(output):
    m = CERT_RE.search(output)
    return m.group(0) if m else None


def extract_verify_code(output):
    m = VERIFY_RE.search(output)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def parse_enddate(enddate_str):
    # OpenSSL liefert z.B. "Aug 12 12:00:00 2027 GMT". %Z ist plattform-
    # abhaengig unzuverlaessig, daher GMT abschneiden und UTC fest annehmen
    # (notAfter wird von openssl x509 immer in GMT/UTC ausgegeben).
    s = enddate_str.strip()
    if s.endswith("GMT"):
        s = s[:-3].strip()
    try:
        dt = datetime.strptime(s, "%b %d %H:%M:%S %Y")
    except ValueError:
        die(NAGIOS_UNKNOWN, f"Unbekanntes Datumsformat von openssl: {enddate_str!r}")
    return dt.replace(tzinfo=timezone.utc)


def get_cert_details(openssl, cert_pem, timeout):
    text = run(
        [openssl, "x509", "-noout", "-enddate", "-subject", "-issuer"],
        timeout,
        input_data=cert_pem.encode(),
    )

    enddate_match = ENDDATE_RE.search(text)
    if not enddate_match:
        die(NAGIOS_UNKNOWN, f"Konnte Ablaufdatum nicht parsen: {text.strip()}")

    subject_match = SUBJECT_RE.search(text)
    issuer_match = ISSUER_RE.search(text)

    enddate = parse_enddate(enddate_match.group(1))
    subject = subject_match.group(1).strip() if subject_match else "unbekannt"
    issuer = issuer_match.group(1).strip() if issuer_match else "unbekannt"
    return enddate, subject, issuer


def main():
    args = parse_args()

    if args.warning <= args.critical:
        die(NAGIOS_UNKNOWN, "--warning muss groesser als --critical sein")

    openssl = find_openssl()
    cmd = build_s_client_command(openssl, args)
    output = run(cmd, args.timeout)

    cert_pem = extract_certificate(output)
    if not cert_pem:
        tail = " / ".join(output.strip().splitlines()[-5:]) or "(keine Ausgabe)"
        die(NAGIOS_UNKNOWN,
            f"Kein Zertifikat von {args.host}:{args.port} erhalten "
            f"(letzte Ausgabe: {tail})")

    enddate, subject, issuer = get_cert_details(openssl, cert_pem, args.timeout)

    now = datetime.now(timezone.utc)
    days_left = (enddate - now).days

    chain_problem = None
    if (args.cafile or args.capath) and not args.no_verify:
        verify_code, verify_reason = extract_verify_code(output)
        if verify_code is None:
            chain_problem = "kein Verify-Ergebnis von openssl erhalten"
        elif verify_code != 0:
            chain_problem = f"Validierung fehlgeschlagen: {verify_reason} (Code {verify_code})"

    perfdata = f"days_left={days_left};{args.warning}:;{args.critical}:;;"
    info = f"subject '{subject}' (issuer '{issuer}') auf {args.host}:{args.port}"

    if days_left < 0:
        die(NAGIOS_CRITICAL,
            f"Zertifikat fuer {info} ist seit {-days_left} Tagen abgelaufen "
            f"({enddate.date()}) | {perfdata}")

    if chain_problem:
        die(NAGIOS_CRITICAL,
            f"Zertifikatskette fuer {info} ungueltig: {chain_problem} "
            f"(laeuft in {days_left} Tagen ab, {enddate.date()}) | {perfdata}")

    if days_left <= args.critical:
        die(NAGIOS_CRITICAL,
            f"Zertifikat fuer {info} laeuft in {days_left} Tagen ab "
            f"({enddate.date()}) | {perfdata}")

    if days_left <= args.warning:
        die(NAGIOS_WARNING,
            f"Zertifikat fuer {info} laeuft in {days_left} Tagen ab "
            f"({enddate.date()}) | {perfdata}")

    die(NAGIOS_OK,
        f"Zertifikat fuer {info} ist noch {days_left} Tage gueltig "
        f"({enddate.date()}) | {perfdata}")


if __name__ == "__main__":
    main()
