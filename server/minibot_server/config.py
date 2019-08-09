import os
import yaml

from typing import Dict, Any, Tuple
from dataclasses import dataclass

def ReadTextFile(*path_args: str) -> str:
    path = os.path.join(*path_args)
    with open(path, mode = "r") as f:
        return f.read()

@dataclass
class ConfigDoc:
    twitch_client_id: str
    twitch_redirect_url: str

def ParseConfigDoc(doc: str) -> ConfigDoc:
    data = yaml.safe_load(doc)
    return ConfigDoc(
        twitch_client_id = data["twitch_client_id"],
        twitch_redirect_url = data["twitch_redirect_url"],
    )

@dataclass
class SecretDoc:
    twitch_client_secret: str

def ParseSecretDoc(doc: str) -> SecretDoc:
    data = yaml.safe_load(doc)
    return SecretDoc(
        twitch_client_secret = data["twitch_client_secret"]
    )

@dataclass
class MinibotConfig:
    config_doc: ConfigDoc
    secret_doc: SecretDoc

def ParseConfigFromHomeDir() -> MinibotConfig:
    """Read the minibot config from the user's home directory.

    This is intended to be used for local development. Files are kept out of the
    github directory to prevent secrets from being comitted.
    """
    homedir = os.environ["HOME"]
    config_yaml = ReadTextFile(homedir, ".config/minibot/config.yaml")
    secret_yaml = ReadTextFile(homedir, ".config/minibot/secret.yaml")

    config_doc = ParseConfigDoc(config_yaml)
    secret_doc = ParseSecretDoc(secret_yaml)

    return MinibotConfig(
        config_doc = config_doc,
        secret_doc = secret_doc,
    )

def ParseConfigFromEtc() -> MinibotConfig:
    """Read the minibot config from the "/etc" directory.

    This is intended to be used during distribution to the cluster. This assumes
    that a ConfigMap with config.yaml is mounted at /etc/minibot/config and the
    a Secrets with secret.yaml is mounted at /etc/minibot/secret
    """
    config_yaml = ReadTextFile("/etc/minibot/config/config.yaml")
    secret_yaml = ReadTextFile("/etc/minibot/secret/secret.yaml")

    config_doc = ParseConfigDoc(config_yaml)
    secret_doc = ParseSecretDoc(secret_yaml)

    return MinibotConfig(
        config_doc = config_doc,
        secret_doc = secret_doc,
    )

def ReadConfig() -> MinibotConfig:
    try:
        return ParseConfigFromHomeDir()
    except FileNotFoundError:
        return ParseConfigFromEtc()