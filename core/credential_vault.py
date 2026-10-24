import os
from typing import Optional, Dict
from cryptography.fernet import Fernet
from core.config import settings
from core.blackboard_memory import BlackboardState
from langgraph.types import interrupt

class CredentialVault:
    def __init__(self):
        # Allow fallback to a deterministic local key for smoke tests if VAULT_MASTER_KEY is not set
        # In production, this MUST be provided via environment variables.
        if settings.VAULT_MASTER_KEY:
            self.key = settings.VAULT_MASTER_KEY.encode()
        else:
            self.key = Fernet.generate_key()

        self.fernet = Fernet(self.key)

    def encrypt(self, data: str) -> str:
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def get_or_request_credential(self, state: BlackboardState, service_name: str, env_var_name: str, setup_url: str) -> str:
        """
        1. Checks OS environment.
        2. Checks Blackboard encrypted vault.
        3. Pauses execution via interrupt() to request from Telegram user if missing.
        """
        # 1. Check OS Env
        env_val = os.getenv(env_var_name)
        if env_val:
            return env_val

        # 2. Check Vault
        encrypted_val = state.vault_data.get(service_name)
        if encrypted_val:
            try:
                decrypted = self.decrypt(encrypted_val)
                os.environ[env_var_name] = decrypted # Inject hot into runtime
                return decrypted
            except Exception as e:
                print(f"Failed to decrypt vault credential for {service_name}: {e}")

        # 3. Request from User (LangGraph Interrupt)
        payload = {
            "type": "credential_request",
            "service_name": service_name,
            "setup_url": setup_url,
            "message": f"⚠️ Agent needs API Key for {service_name}. Get it here: {setup_url}\\nReply on Telegram to securely inject."
        }

        # Pauses execution. When resumed via Command(resume={"api_key": "..."}) this will return.
        user_response = interrupt(payload)

        if not isinstance(user_response, dict) or "api_key" not in user_response:
            raise RuntimeError(f"Failed to acquire credential for {service_name}")

        api_key = user_response["api_key"]

        # Encrypt and save to state
        state.vault_data[service_name] = self.encrypt(api_key)

        # Inject to runtime
        os.environ[env_var_name] = api_key

        return api_key

credential_vault = CredentialVault()
