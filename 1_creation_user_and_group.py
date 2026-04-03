import subprocess
import os
import getpass
import random
import string
import csv
import base64

# --- CONFIGURATION ---
BASE_DN = "dc=cluz,dc=c2lr,dc=eu"
ADMIN_DN = "cn=admin,dc=cluz,dc=c2lr,dc=eu"
ADMIN_PASS = getpass.getpass("Mot de passe admin LDAP : ")

USERS_FILE = "users.txt"
UID_COUNTER_FILE = ".uid_counter"
GID_COUNTER_FILE = ".gid_counter"
CSV_FILE = "/root/creation_utilisateurs/mots_de_passe.csv"

GROUP_GID = {}

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True)

def entry_exists(dn):
    cmd = f"ldapsearch -x -b '{dn}' -LLL"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return "dn:" in result.stdout

def ensure_ou(name):
    dn = f"ou={name},{BASE_DN}"
    if entry_exists(dn):
        return
    ldif = f"""
dn: ou={name},{BASE_DN}
objectClass: organizationalUnit
ou: {name}
"""
    with open(f"/tmp/ou_{name}.ldif", "w") as f:
        f.write(ldif)
    run(f"ldapadd -x -D '{ADMIN_DN}' -w '{ADMIN_PASS}' -f /tmp/ou_{name}.ldif")

def get_next_uid():
    if not os.path.exists(UID_COUNTER_FILE):
        with open(UID_COUNTER_FILE, "w") as f:
            f.write("20100")
    with open(UID_COUNTER_FILE, "r") as f:
        uid = int(f.read().strip())
    next_uid = uid + 1
    with open(UID_COUNTER_FILE, "w") as f:
        f.write(str(next_uid))
    return uid

def get_next_gid():
    if not os.path.exists(GID_COUNTER_FILE):
        with open(GID_COUNTER_FILE, "w") as f:
            f.write("10050")
    with open(GID_COUNTER_FILE, "r") as f:
        gid = int(f.read().strip())
    next_gid = gid + 1
    with open(GID_COUNTER_FILE, "w") as f:
        f.write(str(next_gid))
    return gid

def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

def create_ldap_group(groupname):
    gid = get_next_gid()
    GROUP_GID[groupname] = gid
    dn = f"cn={groupname},ou=Groups,{BASE_DN}"

    if entry_exists(dn):
        print(f"✔️ Groupe {groupname} existe déjà")
        return

    ldif = f"""
dn: {dn}
objectClass: posixGroup
cn: {groupname}
gidNumber: {gid}
"""
    with open(f"/tmp/{groupname}.ldif", "w") as f:
        f.write(ldif)
    run(f"ldapadd -x -D '{ADMIN_DN}' -w '{ADMIN_PASS}' -f /tmp/{groupname}.ldif")

def create_ldap_user(username, email, ip_debut, ip_fin, id_debut, id_fin, groupname, writer):
    dn = f"uid={username},ou=People,{BASE_DN}"

    if entry_exists(dn):
        print(f"⚠️ Utilisateur {username} existe déjà, ignoré")
        return

    uid = get_next_uid()
    gid = GROUP_GID[groupname]

    password_plain = generate_password()

    ldif = f"""
dn: {dn}
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: {username}
cn: {username}
sn: {username}
givenName: {username}
mail: {email}
uidNumber: {uid}
gidNumber: {gid}
homeDirectory: /home/{username}
loginShell: /bin/bash
userPassword: {password_plain}
"""
    with open(f"/tmp/{username}.ldif", "w") as f:
        f.write(ldif)

    result = run(f"ldapadd -x -D '{ADMIN_DN}' -w '{ADMIN_PASS}' -f /tmp/{username}.ldif")

    if result.returncode == 0:
        # On écrit aussi les plages IP et ID dans le CSV
        writer.writerow([username, password_plain, email, ip_debut, ip_fin, id_debut, id_fin])
        print(f"✅ OK : {username} créé (IP: {ip_debut} -> {ip_fin} | ID: {id_debut} -> {id_fin})")
    else:
        print(f"❌ ERREUR LDAP pour {username} : {result.stderr.decode().strip()}")

def import_users_into_group(groupname):
    if not os.path.exists(USERS_FILE):
        print("❌ users.txt introuvable.")
        return

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["login", "password", "email", "ip_debut", "ip_fin", "id_debut", "id_fin"])

        print(f"👤 Traitement des utilisateurs pour le groupe : {groupname}...")
        with open(USERS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = [p.strip() for p in line.split(",")]

                # Format attendu : login,email,ip_debut,ip_fin,id_debut,id_fin
                if len(parts) == 6:
                    login, email, ip_debut, ip_fin, id_debut, id_fin = parts
                    create_ldap_user(login, email, ip_debut, ip_fin, id_debut, id_fin, groupname, writer)

                # Format minimal sans plages (rétrocompatibilité) : login,email
                elif len(parts) == 2:
                    login, email = parts
                    create_ldap_user(login, email, "", "", "", "", groupname, writer)

                else:
                    print(f"⚠️ Ligne ignorée (format invalide) : {line}")

        csvfile.flush()
        os.fsync(csvfile.fileno())

    print("\n✅ Opération terminée.")
    print(f"📁 Fichier généré : {CSV_FILE}")

    print("--- Contenu du fichier CSV ---")
    with open(CSV_FILE, "r") as check:
        print(check.read())
    print("------------------------------")

def main():
    ensure_ou("People")
    ensure_ou("Groups")

    groupname = input("🆕 Nom du groupe LDAP : ").strip()
    create_ldap_group(groupname)
    import_users_into_group(groupname)

if __name__ == "__main__":
    main()
