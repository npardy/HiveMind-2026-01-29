"""
Config Loader - Centralized configuration management
Loads config.yaml and provides typed access to all settings.
"""

import os
import yaml
from typing import Optional

# Default config path (can be overridden via environment variable)
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


class Config:
    """Singleton config holder - load once, access anywhere."""
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: str = None):
        """Load config from YAML file."""
        path = config_path or os.environ.get("HIVE_MIND_CONFIG", DEFAULT_CONFIG_PATH)
        with open(path, 'r') as f:
            self._config = yaml.safe_load(f)
        return self

    @property
    def config(self) -> dict:
        if self._config is None:
            self.load()
        return self._config

    # =========================================================================
    # NAS / File Paths
    # =========================================================================
    @property
    def base_path(self) -> str:
        return self.config.get("nas", {}).get("base_path", "Z:\\")

    @property
    def jobs_folder(self) -> str:
        return self.config.get("nas", {}).get("jobs_folder", "Z:\\Jobs")

    @property
    def data_sync_folder(self) -> str:
        return self.config.get("nas", {}).get("data_sync_folder", "Z:\\Data Sync\\office-jobs")

    @property
    def proposals_folder(self) -> str:
        return self.config.get("nas", {}).get("proposals_folder", "Z:\\Pardy Surveys\\Proposals")

    @property
    def flagged_folder(self) -> str:
        return self.config.get("nas", {}).get("flagged_folder", "H:\\flagged")

    @property
    def job_index_file(self) -> str:
        return self.config.get("nas", {}).get("job_index_file", "H:\\data\\job_index.json")

    @property
    def proposal_index_file(self) -> str:
        return self.config.get("nas", {}).get("proposal_index_file", "H:\\data\\proposal_index.json")

    @property
    def token_cache_graph(self) -> str:
        return self.config.get("nas", {}).get("token_cache_graph", "H:\\data\\graph_token_cache_v2.json")

    @property
    def token_cache_qbo(self) -> str:
        return self.config.get("nas", {}).get("token_cache_qbo", "H:\\data\\qbo_token_cache.json")

    @property
    def notification_queue(self) -> str:
        return self.config.get("nas", {}).get("notification_queue", "Z:\\Data Sync\\notifications\\events.jsonl")

    @property
    def signatures_folder(self) -> str:
        return self.config.get("nas", {}).get("signatures_folder", "H:\\signatures")

    # =========================================================================
    # Email Settings
    # =========================================================================
    @property
    def email_client_id(self) -> str:
        return self.config.get("email", {}).get("client_id", "")

    @property
    def email_client_secret(self) -> str:
        return self.config.get("email", {}).get("client_secret", "")

    @property
    def email_redirect_uri(self) -> str:
        return self.config.get("email", {}).get("redirect_uri", "http://localhost:8000/callback")

    @property
    def email_check_interval(self) -> int:
        return self.config.get("email", {}).get("check_interval_seconds", 60)

    @property
    def email_headless(self) -> bool:
        return self.config.get("email", {}).get("headless", False)

    # =========================================================================
    # Anthropic Settings
    # =========================================================================
    @property
    def anthropic_api_key(self) -> str:
        return self.config.get("anthropic", {}).get("api_key", "")

    @property
    def anthropic_model(self) -> str:
        return self.config.get("anthropic", {}).get("model", "claude-sonnet-4-5-20250929")

    # =========================================================================
    # QuickBooks Settings
    # =========================================================================
    @property
    def qbo_client_id(self) -> str:
        return self.config.get("quickbooks", {}).get("client_id", "")

    @property
    def qbo_client_secret(self) -> str:
        return self.config.get("quickbooks", {}).get("client_secret", "")

    @property
    def qbo_redirect_uri(self) -> str:
        return self.config.get("quickbooks", {}).get("redirect_uri", "")

    @property
    def qbo_environment(self) -> str:
        return self.config.get("quickbooks", {}).get("environment", "production")

    # =========================================================================
    # Processing Settings
    # =========================================================================
    @property
    def known_lawyer_domains(self) -> list:
        return self.config.get("processing", {}).get("known_lawyer_domains", [])

    @property
    def log_level(self) -> str:
        return self.config.get("logging", {}).get("level", "INFO")

    @property
    def log_file(self) -> str:
        return self.config.get("logging", {}).get("file", "H:\\logs\\email_automation.log")


# Global config instance
config = Config()


def get_config() -> Config:
    """Get the global config instance."""
    return config
