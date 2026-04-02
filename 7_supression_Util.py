#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import getpass
import sys
import os

# ─── CONFIG ───────────────────────────────────────────────
LDAP_BASE_DN   = "dc=cluz,dc=c2lr,dc=eu"
LDAP_ADMIN_DN  = "cn=admin,dc=cluz,dc=c2lr,dc=eu"
LDAP_HOST      = "ldapi:///"
LDAP_USER_OU   = "ou=people"
HTPASSWD_HOST  = "10.0.0.17"
HTPASSWD_USER  = "httpauthadm"
HTPASSWD_FILE  = "/etc/nginx/.htpasswd"
PROXMOX_HOST   = "10.0.0.11"
PROXMOX_USER   = "root"
PROXMOX_REALM  = "ldap-c2lr"
SUPP_FILE      = "supp.txt"
# ──────────────────────────────────────────────────────────

# ─── Lecture du fichier supp.txt ──────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
supp_path  = os.path.join(script_dir, SUPP_FILE)

if not os.path.exists(supp_path):
    print(f"[ERREUR] Fichier '{SUPP_FILE}' introuvable dans {script_dir}")
    sys.exit(1)

with open(supp_path, "r") as f:
    uids = [line.strip() for line in f if line.strip()]

if not uids:
    print(f"[ERREUR] Le fichier '{SUPP_FILE}' est vide.")
    sys.exit(1)

print("=" * 55)
print("   Suppression d'utilisateurs")
print("=" * 55)
print(f"\n[*] Utilisateurs à supprimer ({len(uids)}) :")
for uid in uids:
    print(f"    - {uid}")

# ─── Saisie des mots de passe ─────────────────────────────
print()
ldap_admin_pw   = getpass.getpass("[?] Mot de passe admin OpenLDAP : ")
htpasswd_ssh_pw = getpass.getpass("[?] Mot de passe SSH httpauthadm : ")
proxmox_ssh_pw  = getpass.getpass("[?] Mot de passe SSH root Proxmox : ")

# ─── Traitement par UID ───────────────────────────────────
errors = []

for uid in uids:
    print(f"\n{'─'*55}")
    print(f"  Traitement de : {uid}")
    print(f"{'─'*55}")

    # 1. Suppression dans OpenLDAP
    print(f"[*] Suppression dans OpenLDAP...")
    result = subprocess.run(
        [
            "ldapdelete",
            "-H", LDAP_HOST,
            "-x",
            "-D", LDAP_ADMIN_DN,
            "-w", ldap_admin_pw,
            f"uid={uid},{LDAP_USER_OU},{LDAP_BASE_DN}"
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        msg = f"[ERREUR] OpenLDAP ({uid}) : {result.stderr.strip()}"
        print(msg)
        errors.append(msg)
    else:
        print(f"[OK] OpenLDAP : {uid} supprimé.")

    # 2. Suppression dans .htpasswd via SSH
    print(f"[*] Suppression dans .htpasswd via SSH...")
    result = subprocess.run(
        [
            "sshpass", "-p", htpasswd_ssh_pw,
            "ssh", "-o", "StrictHostKeyChecking=no",
            f"{HTPASSWD_USER}@{HTPASSWD_HOST}",
            f"htpasswd -D {HTPASSWD_FILE} {uid}"
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        msg = f"[ERREUR] htpasswd ({uid}) : {result.stderr.strip()}"
        print(msg)
        errors.append(msg)
    else:
        print(f"[OK] .htpasswd : {uid} supprimé.")

    # 3. Proxmox via SSH
    print(f"[*] Traitement dans Proxmox...")

    # Commandes Proxmox enchaînées
    proxmox_cmds = " && ".join([
        # Resync LDAP realm
        f"pveum realm sync {PROXMOX_REALM}",
        # Suppression de la permission
        f"pveum acl delete /pool/pool-{uid} --user {uid}@{PROXMOX_REALM} --roles PVEPoolUser",
        # Suppression du pool
        f"pveum pool delete pool-{uid}"
    ])

    result = subprocess.run(
        [
            "sshpass", "-p", proxmox_ssh_pw,
            "ssh", "-o", "StrictHostKeyChecking=no",
            f"{PROXMOX_USER}@{PROXMOX_HOST}",
            proxmox_cmds
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        msg = f"[ERREUR] Proxmox ({uid}) : {result.stderr.strip()}"
        print(msg)
        errors.append(msg)
    else:
        print(f"[OK] Proxmox : sync, permission et pool supprimés pour {uid}.")

# ─── Résumé final ─────────────────────────────────────────
print(f"\n{'='*55}")
if errors:
    print(f"  Terminé avec {len(errors)} erreur(s) :")
    for e in errors:
        print(f"  ⚠  {e}")
else:
    print(f"  Tous les utilisateurs ont été supprimés avec succès ✔")
print(f"{'='*55}")
