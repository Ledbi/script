#!/usr/bin/env python3
import getpass
import paramiko
import sys
import os
import json

# ================= CONFIGURATION =================
HOST = "pveZ1"
USER_SSH = "root"  
ROLE = "DroitUtilisateur"
GROUP_NAME = "utilisateurs"
REALM = "ldap-c2lr"
USERS_FILE = "users.txt"
# =================================================

class ProxmoxManager:
    def __init__(self, host, user, password):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(host, username=user, password=password)
            print(f"✅ Connecté à {host}")
        except Exception as e:
            sys.exit(f"❌ Erreur de connexion SSH : {e}")

    def run_remote(self, cmd, ignore_error=False):
        """Exécute une commande sur le serveur distant via SSH."""
        print(f"-> Executing: {cmd}")
        stdin, stdout, stderr = self.client.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        if err and not ignore_error and "already exists" not in err:
            print(f"[ERREUR] {err}")
        return out

    def manage_user_group(self, userid):
        """Gère l'ajout au groupe Proxmox sur le serveur distant."""
        if GROUP_NAME not in self.run_remote("pveum group list", True):
            self.run_remote(f"pveum group add {GROUP_NAME}")
        
        output = self.run_remote(f"pveum user list --userid {userid} --output-format json", True)
        current_groups = ""
        if output:
            try:
                user_data = json.loads(output)
                current_groups = user_data[0].get("groups", "")
            except: pass
        
        group_list = [g.strip() for g in current_groups.split(',') if g.strip()]
        if GROUP_NAME not in group_list:
            group_list.append(GROUP_NAME)
            self.run_remote(f"pveum user modify {userid} --groups {','.join(group_list)}")

    def process_user(self, line):
        line = line.strip()
        if not line: return
        
        # Extraction du login avant la virgule
        user = line.split(',')[0].strip() 
        full_id = f"{user}@{REALM}"
        
        # Vérification si l'utilisateur existe dans PVE
        if full_id not in self.run_remote("pveum user list"):
            print(f"[SKIP] {full_id} non trouvé sur le serveur.")
            return

        pool_name = f"pool-{user}"

        print(f"\n>>> CONFIGURATION DISTANTE : {user.upper()}")

        # --- 1. Variante Création de Pool (pveum pool add) ---
        # On vérifie si le pool existe déjà avant d'essayer de l'ajouter
        check_pool = self.run_remote(f"pveum pool list", True)
        if pool_name not in check_pool:
            self.run_remote(f"pveum pool add {pool_name}")
            print(f"✅ Pool '{pool_name}' créé.")
        else:
            print(f"ℹ Pool '{pool_name}' existe déjà.")
        
        # 2. Groupe
        self.manage_user_group(full_id)
        
        # 3. ACL (On force l'application des droits sur le pool)
        self.run_remote(f"pveum aclmod /pool/{pool_name} --user {full_id} --role {ROLE} --propagate 1")
        
        print(f"✔ Terminé pour {user}.")

def main():
    print("⚠️  Avez-vous bien pensé à sync le realm sur Proxmox ?")
    password = getpass.getpass(f"Mot de passe pour {USER_SSH}@{HOST} : ")

    if not os.path.exists(USERS_FILE):
        sys.exit(f"ERREUR : {USERS_FILE} manquant localement.")

    pve = ProxmoxManager(HOST, USER_SSH, password)

    with open(USERS_FILE, "r") as f:
        for line in f:
            pve.process_user(line)

    pve.client.close()
    print("\n🚀 Opération terminée.")

if __name__ == "__main__":
    main()
