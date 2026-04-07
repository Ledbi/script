import subprocess
import getpass
import os
import csv
import shlex

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
REMOTE_NGINX_IP = "10.0.0.17"
REMOTE_VPN_IP = "10.0.0.20"
USER_NGINX = "httpauthadm"
USER_VPN = "root"

HTPASSWD_PATH = "/etc/nginx/.htpasswd"
WG_CONF_PATH = "/etc/wireguard/wg0.conf"
USER_FOLDER = "/root/creation_utilisateurs"
USER_SOURCE_FILE = os.path.join(USER_FOLDER, "mots_de_passe.csv")

IP_STORAGE_FILE = os.path.join(USER_FOLDER, "utilisees.txt")

SERVER_PUB_KEY = "Vjiy6Y1/wZzngkGJmHsoUiW9GMJ33/fTyXTYWr70MBg="

# ==============================================================================
# --- FONCTIONS TECHNIQUES ---
# ==============================================================================

def run_remote_cmd(ip, user, command, admin_pass=None):
    """Exécute une commande SSH à distance avec gestion optionnelle du mot de passe."""
    if admin_pass:
        env = os.environ.copy()
        env["SSHPASS"] = admin_pass
        full_ssh_command = [
            "sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no",
            f"{user}@{ip}", command
        ]
        return subprocess.run(full_ssh_command, capture_output=True, text=True, env=env)
    else:
        full_ssh_command = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            f"{user}@{ip}", command
        ]
        return subprocess.run(full_ssh_command, capture_output=True, text=True)

# ==============================================================================
# --- PROGRAMME PRINCIPAL ---
# ==============================================================================

def main():
    print(f"--- 🚀 DÉMARRAGE DU SCRIPT INTÉGRAL ---")

    # 1. Préparation de l'environnement local
    if not os.path.exists(USER_FOLDER):
        os.makedirs(USER_FOLDER)
        print(f"[LOG] Dossier de travail créé : {USER_FOLDER}")

    if not os.path.exists(IP_STORAGE_FILE):
        with open(IP_STORAGE_FILE, "w") as f:
            f.write("19")
        print(f"[LOG] Fichier de mémoire IP initialisé (Début à .20)")

    if not os.path.exists(USER_SOURCE_FILE):
        print(f"❌ ERREUR : Le fichier {USER_SOURCE_FILE} est introuvable.")
        print(f"Veuillez créer le fichier avec les colonnes : login, password, email")
        return

    # 2. Authentification SSH
    pass_nginx = getpass.getpass(f"🔑 Mot de passe SSH pour {USER_NGINX}@{REMOTE_NGINX_IP} : ")

    # 3. Lecture des données CSV
    try:
        with open(USER_SOURCE_FILE, "r") as f:
            reader = list(csv.reader(f))
    except Exception as e:
        print(f"❌ ERREUR lors de la lecture du CSV : {e}")
        return

    if len(reader) < 2:
        print("⚠️ Le fichier CSV est vide ou ne contient que l'en-tête.")
        return

    header = [h.strip().lower() for h in reader[0]]
    rows = reader[1:]
    updated_rows = []

    # 4. Lecture du compteur d'IP permanent
    try:
        with open(IP_STORAGE_FILE, "r") as f:
            current_last_suffix = int(f.read().strip())
    except:
        current_last_suffix = 19

    next_ip_suffix = current_last_suffix + 1

    # 5. Traitement de chaque utilisateur
    for row in rows:
        if not row or len(row) < 3:
            continue

        u = row[header.index("login")].strip()
        p = row[header.index("password")].strip()
        e = row[header.index("email")].strip()

        # Récupération des plages IP et ID (vides si absentes du CSV)
        def get_col(col_name):
            if col_name in header:
                idx = header.index(col_name)
                return row[idx].strip() if len(row) > idx else ""
            return ""

        ip_debut       = get_col("ip_debut")
        ip_fin         = get_col("ip_fin")
        id_debut       = get_col("id_debut")
        id_fin         = get_col("id_fin")

        print(f"\n--- 👤 TRAITEMENT DE : {u} ---")

        # Gestion de l'IP VPN assignée
        existing_ip = get_col("allowed_ip")

        if existing_ip:
            client_ip = existing_ip
            print(f"      📍 IP existante détectée : {client_ip}")
        else:
            client_ip = f"192.168.110.{next_ip_suffix}/32"
            print(f"      📍 Attribution d'une nouvelle IP : {client_ip}")
            with open(IP_STORAGE_FILE, "w") as f:
                f.write(str(next_ip_suffix))
            next_ip_suffix += 1

        try:
            # --- ÉTAPE A : NGINX ---
            cmd_nginx = f"htpasswd -b {HTPASSWD_PATH} {shlex.quote(u)} {shlex.quote(p)}"

            print(f"      🌐 Mise à jour NGINX ({REMOTE_NGINX_IP})...")
            res_n = run_remote_cmd(REMOTE_NGINX_IP, USER_NGINX, cmd_nginx, pass_nginx)

            if res_n.returncode != 0:
                print(f"      ❌ Erreur NGINX : {res_n.stderr.strip()}")
                if res_n.stdout.strip():
                    print(f"      ℹ️  stdout : {res_n.stdout.strip()}")
                updated_rows.append(row)
                continue
            else:
                print(f"      ✅ NGINX mis à jour avec succès.")

            # --- ÉTAPE B : VPN (WIREGUARD) ---
            print(f"      🔐 Génération des clés VPN...")
            res_priv = run_remote_cmd(REMOTE_VPN_IP, USER_VPN, "wg genkey")
            if res_priv.returncode != 0:
                print(f"      ❌ Erreur génération clé privée : {res_priv.stderr.strip()}")
                updated_rows.append(row)
                continue

            priv_key = res_priv.stdout.strip()

            res_pub = run_remote_cmd(
                REMOTE_VPN_IP, USER_VPN,
                f"echo {shlex.quote(priv_key)} | wg pubkey"
            )
            if res_pub.returncode != 0:
                print(f"      ❌ Erreur génération clé publique : {res_pub.stderr.strip()}")
                updated_rows.append(row)
                continue

            pub_key = res_pub.stdout.strip()

            if not existing_ip:
                print(f"      📡 Enregistrement du Peer VPN...")
                cmd_vpn = (
                    f"echo -e '\\n# User: {u}\\n[Peer]\\nPublicKey = {pub_key}\\nAllowedIPs = {client_ip}' "
                    f">> {WG_CONF_PATH} && wg syncconf wg0 <(wg-quick strip wg0)"
                )
                res_vpn = run_remote_cmd(REMOTE_VPN_IP, USER_VPN, f"bash -c {shlex.quote(cmd_vpn)}")
                if res_vpn.returncode != 0:
                    print(f"      ❌ Erreur VPN syncconf : {res_vpn.stderr.strip()}")
                else:
                    print(f"      ✅ VPN activé pour {u}.")

            # --- ÉTAPE C : SAUVEGARDE LOCALE (CSV) ---
            # On conserve toutes les colonnes, y compris ip_debut/ip_fin/id_debut/id_fin
            updated_rows.append([
                u, p, e,
                priv_key, pub_key, SERVER_PUB_KEY, client_ip,
                ip_debut, ip_fin, id_debut, id_fin
            ])

            with open(USER_SOURCE_FILE, "w", newline='') as f_out:
                writer = csv.writer(f_out)
                writer.writerow([
                    "login", "password", "email",
                    "private_key", "public_key", "server_public_key", "allowed_ip",
                    "ip_debut", "ip_fin", "id_debut", "id_fin"
                ])
                writer.writerows(updated_rows)
            print(f"      💾 Données enregistrées dans {USER_SOURCE_FILE}")

        except Exception as err:
            print(f"      ❌ ERREUR lors du traitement de {u} : {err}")
            updated_rows.append(row)

    print(f"\n--- 🏁 FIN DU SCRIPT ---")
    print(f"Dernière IP utilisée enregistrée dans : {IP_STORAGE_FILE}")

if __name__ == "__main__":
    main()
