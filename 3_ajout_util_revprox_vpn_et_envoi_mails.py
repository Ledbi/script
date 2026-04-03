import subprocess
import getpass
import os
import smtplib
import time
import csv
import secrets
import string
from email.message import EmailMessage

# --- CONFIGURATION SSH / NGINX ---
REMOTE_IP = "10.0.0.17"
REMOTE_USER = "httpauthadm"
HTPASSWD_PATH = "/etc/nginx/.htpasswd"
USER_SOURCE_FILE = "/root/creation_utilisateurs/mots_de_passe.csv"

# --- CONFIGURATION SMTP KOLAB (C2LR) ---
SMTP_SERVER = "smtp.c2lr.fr"
SMTP_PORT = 587
SENDER_EMAIL = "cluz@c2lr.fr"
SENDER_PASSWORD = "OIP4WX7xYIUa0zx"

def send_confirmation_mail(username, password, dest_email):
    """Envoie les identifiants via le serveur SMTP Kolab."""
    msg = EmailMessage()
    msg.set_content(f"Bonjour,\n\nTes accès au Reverse Proxy ont été configurés :\n\nLogin: {username}\nMot de passe: {password}\n\nL'administration.")
    msg['Subject'] = f"Accès créé : {username}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = dest_email

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"📧 Mail envoyé avec succès à {dest_email}")
    except Exception as e:
        print(f"❌ Erreur SMTP Kolab : {e}")

def run_remote_cmd(admin_pass, user_to_add, pass_to_add, email_dest):
    """Crée l'accès sur Nginx via SSH."""
    remote_command = f"htpasswd -b {HTPASSWD_PATH} {user_to_add} {pass_to_add}"
    full_ssh_command = [
        "sshpass", "-p", admin_pass,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{REMOTE_USER}@{REMOTE_IP}",
        remote_command
    ]

    try:
        subprocess.run(full_ssh_command, capture_output=True, text=True, check=True)
        print(f"✅ Utilisateur {user_to_add} ajouté sur Nginx.")
        send_confirmation_mail(user_to_add, pass_to_add, email_dest)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur SSH : {e.stderr.strip()}")

def main():
    if not os.path.exists(USER_SOURCE_FILE):
        print(f"Fichier {USER_SOURCE_FILE} introuvable.")
        return

    admin_pass = getpass.getpass("Mot de passe SSH (10.0.0.17) : ")

    with open(USER_SOURCE_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(",")

            # Ignore la ligne d'en-tête (supporte "login" et "username")
            if parts[0].lower() in ("login", "username"):
                continue

            # On prend les 3 premiers champs : login, password, email
            # Les colonnes suivantes (ip_debut, ip_fin, id_debut, id_fin, etc.)
            # sont ignorées ici car ce script ne les utilise pas
            if len(parts) >= 3:
                u = parts[0].strip()
                p = parts[1].strip()
                e = parts[2].strip()

                run_remote_cmd(admin_pass, u, p, e)

                print(f"⏳ Cooldown 5s...")
                time.sleep(5)
            else:
                print(f"⚠️ Ligne malformée (colonnes manquantes) : {line}")

if __name__ == "__main__":
    main()
