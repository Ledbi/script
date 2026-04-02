#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import getpass
import sys

# ─── CONFIG ───────────────────────────────────────────────
LDAP_BASE_DN  = "dc=cluz,dc=c2lr,dc=eu"
LDAP_ADMIN_DN = "cn=admin,dc=cluz,dc=c2lr,dc=eu"
LDAP_HOST     = "ldapi:///"
LDAP_USER_OU  = "ou=people"
HTPASSWD_HOST = "10.0.0.17"
HTPASSWD_USER = "httpauthadm"
HTPASSWD_FILE = "/etc/nginx/.htpasswd"
# ──────────────────────────────────────────────────────────

print("=" * 50)
print("   Modification de mot de passe")
print("=" * 50)

uid = input("\n[?] UID de l'utilisateur : ").strip()
if not uid:
    print("[ERREUR] UID vide.")
    sys.exit(1)

new_password = getpass.getpass("[?] Nouveau mot de passe : ")
if not new_password:
    print("[ERREUR] Mot de passe vide.")
    sys.exit(1)

ldap_admin_pw   = getpass.getpass("[?] Mot de passe admin OpenLDAP : ")
htpasswd_ssh_pw = getpass.getpass("[?] Mot de passe SSH httpauthadm : ")

# 1. Modification OpenLDAP
print("\n[*] Modification dans OpenLDAP...")
result = subprocess.run(
    [
        "ldappasswd",
        "-H", LDAP_HOST,
        "-x",
        "-D", LDAP_ADMIN_DN,
        "-w", ldap_admin_pw,
        "-s", new_password,
        f"uid={uid},{LDAP_USER_OU},{LDAP_BASE_DN}"
    ],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"[ERREUR] OpenLDAP : {result.stderr.strip()}")
    sys.exit(1)
print("[OK] OpenLDAP mis à jour.")

# 2. Modification htpasswd via SSH en passant le mdp via stdin
# htpasswd -i lit le mot de passe depuis stdin (pas d'argument en clair)
print("[*] Modification dans .htpasswd via SSH...")

# On envoie : "mot_de_passe\nmot_de_passe\n" sur stdin de htpasswd -i
htpasswd_input = f"{new_password}\n{new_password}\n"

ssh_cmd = [
    "sshpass", "-p", htpasswd_ssh_pw,
    "ssh", "-o", "StrictHostKeyChecking=no",
    f"{HTPASSWD_USER}@{HTPASSWD_HOST}",
    f"htpasswd -i {HTPASSWD_FILE} {uid}"
]

result = subprocess.run(
    ssh_cmd,
    input=htpasswd_input,
    capture_output=True,
    text=True
)
if result.returncode != 0:
    print(f"[ERREUR] htpasswd : {result.stderr.strip()}")
    sys.exit(1)
print("[OK] .htpasswd mis à jour.")

print("\n" + "=" * 50)
print(f"  Succès pour l'utilisateur : {uid}")
print("=" * 50)
