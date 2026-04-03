import csv
import smtplib
import os
import getpass
from email.message import EmailMessage

# --- CONFIGURATION ---
USER_SOURCE_FILE = "/root/creation_utilisateurs/mots_de_passe.csv"

# --- CONFIGURATION SMTP ---
SMTP_SERVER = "smtp.c2lr.fr"
SMTP_PORT = 587
SENDER_EMAIL = "cluz@c2lr.fr"

def send_user_mail(login, password, priv_key, pub_key, server_pub_key, allowed_ip,
                   ip_debut, ip_fin, id_debut, id_fin, dest_email, smtp_password):
    msg = EmailMessage()

    content = (
        f"Bonjour,\n\n"
        f"Voici vos paramètres de connexion personnels :\n\n"
        f"--- ACCÈS GÉNÉRAUX ---\n"
        f"Login : {login}\n"
        f"Mot de passe : {password}\n\n"
        f"--- CONFIGURATION VPN WIREGUARD ---\n"
        f"Votre IP VPN assignée : {allowed_ip}\n"
        f"Votre Private Key : {priv_key}\n"
        f"Votre Public Key : {pub_key}\n"
        f"Server Public Key : {server_pub_key}\n\n"
        f"--- PLAGES RÉSEAU ---\n"
        f"IP début : {ip_debut}\n"
        f"IP fin   : {ip_fin}\n\n"
        f"--- PLAGES ID ---\n"
        f"ID début : {id_debut}\n"
        f"ID fin   : {id_fin}\n\n"
        f"Cordialement,\n"
        f"L'administration réseau."
    )

    msg.set_content(content)
    msg['Subject'] = f"Plateforme CLUZ - Vos accès personnels : {login}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = dest_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SENDER_EMAIL, smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"\n❌ Erreur lors de l'envoi à {dest_email} : {e}")
        return False

def main():
    if not os.path.exists(USER_SOURCE_FILE):
        print(f"❌ Erreur : Le fichier {USER_SOURCE_FILE} est introuvable.")
        return

    print(f"Configuration de l'envoi pour : {SENDER_EMAIL}")
    password_input = getpass.getpass(prompt="Entrez le mot de passe SMTP : ")

    if not password_input:
        print("❌ Erreur : Le mot de passe ne peut pas être vide.")
        return

    print(f"📧 Début de l'envoi des e-mails depuis {USER_SOURCE_FILE}...")

    try:
        with open(USER_SOURCE_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            required_cols = [
                'login', 'password', 'email',
                'private_key', 'public_key', 'server_public_key', 'allowed_ip',
                'ip_debut', 'ip_fin', 'id_debut', 'id_fin'
            ]

            if not all(col in reader.fieldnames for col in required_cols):
                print(f"❌ Erreur : Le CSV doit contenir les colonnes : {', '.join(required_cols)}")
                return

            count = 0
            for row in reader:
                login = row['login'].strip()
                email = row['email'].strip()

                if not email or "@" not in email:
                    print(f"⚠️ Email invalide pour {login}, passage à l'utilisateur suivant.")
                    continue

                print(f"✉️ Envoi à {login} ({email})...", end=" ", flush=True)

                success = send_user_mail(
                    login=login,
                    password=row['password'].strip(),
                    priv_key=row['private_key'].strip(),
                    pub_key=row['public_key'].strip(),
                    server_pub_key=row['server_public_key'].strip(),
                    allowed_ip=row['allowed_ip'].strip(),
                    ip_debut=row['ip_debut'].strip(),
                    ip_fin=row['ip_fin'].strip(),
                    id_debut=row['id_debut'].strip(),
                    id_fin=row['id_fin'].strip(),
                    dest_email=email,
                    smtp_password=password_input
                )

                if success:
                    print("✅ Envoyé")
                    count += 1

            print(f"\n✨ Terminé. {count} e-mails ont été envoyés avec succès.")

    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier : {e}")

if __name__ == "__main__":
    main()
