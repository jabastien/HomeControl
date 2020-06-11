"""config_manager module"""

import logging
import os
from collections import defaultdict

import voluptuous as vol
from homecontrol.dependencies.yaml_loader import YAMLLoader
from homecontrol.exceptions import (ConfigDomainAlreadyRegistered,
                                    ConfigurationNotApproved)

LOGGER = logging.getLogger(__name__)


class ConfigManager:
    """
    ConfigManager

    Manages the configuration with configuration domains
    """

    def __init__(self, cfg: dict, cfg_path: str) -> None:
        self.cfg = cfg
        self.cfg_path = cfg_path
        self.registered_handlers = {}
        self.registered_domains = set()
        self.domain_schemas = {}
        self.domain_reloadable = defaultdict(bool)

    def get(self, key, default=None):
        """getter for self.cfg"""
        return self.cfg.get(key, default)

    def __getitem__(self, key):
        return self.cfg[key]

    async def reload_config(self) -> None:
        """Reloads the configuration and updates where it can"""
        cfg = YAMLLoader.load(
            open(self.cfg_path), cfg_folder=os.path.dirname(self.cfg_path))

        LOGGER.info("Updating the configuration")
        for domain, domain_config in cfg.items():
            if domain_config != self.cfg.get(domain, None):
                LOGGER.info("New configuration detected for domain %s", domain)

                if not self.domain_reloadable[domain]:
                    LOGGER.error(
                        "Configuration domain %s is not reloadable", domain)
                    continue
                try:
                    domain_config = await self.approve_domain_config(
                        domain,
                        domain_config,
                        initial=False)
                except (vol.Error, ConfigurationNotApproved):
                    continue

                self.cfg[domain] = domain_config

                if hasattr(self.registered_handlers.get(domain, None),
                           "apply_new_configuration"):
                    handler = self.registered_handlers[domain]
                    await handler.apply_new_configuration(
                        domain, domain_config)

                LOGGER.info("Configuration for domain %s updated", domain)

        LOGGER.info("Completed updating the configuration")

    async def approve_domain_config(self,
                                    domain: str,
                                    config: dict,
                                    initial: bool = True) -> dict:
        """
        Returns an approved and validated version of config for a domain
        """
        if domain in self.domain_schemas:  # Validate new configuration
            try:
                config = self.domain_schemas[domain](config)
            except vol.Error as e:
                LOGGER.error(
                    "Configuration for domain %s is invalid",
                    domain,
                    exc_info=True)
                raise e

        # Check if the domain owner approves
        if hasattr(self.registered_handlers.get(domain, None),
                   "approve_configuration"):
            handler = self.registered_handlers[domain]
            result = await handler.approve_configuration(config)
            # pylint: disable=singleton-comparison
            # None should be accepted
            if result == False:  # noqa: E712
                LOGGER.warning(
                    "Configuration for domain %s not approved", domain)
                raise ConfigurationNotApproved(domain)

        return config

    async def register_domain(self,
                              domain: str,
                              handler: object = None,
                              schema: vol.Schema = None,
                              allow_reload: bool = False,
                              default: dict = None) -> object:
        """
        Registers a configuration domain

        Objects can register themselves to their own configuration domain and
        subscribe to changes in the configuration

        Args:
            domain (str):
                The configuration domain (A top-level key in config.yaml)
            handler (object):
                The object subscribing to this domain.
                Methods it can implement are:
                - approve_configuration(domain, config) -> bool:
                - apply_new_configuration(domain, config) -> None:
                If not specified then your
                configuration domain will not be reloadable
        allow_reload (bool):
            Allow reloading this configuration domain
        schema (voluptuous.Schema):
            Schema to validate the configuration and to fill in defaults
        default (dict):
            A default configuration

        Returns:
            A validated and approved version of the configuration
        """
        default = {} if default is None else default
        if domain in self.registered_domains:
            raise ConfigDomainAlreadyRegistered(
                f"The configuration domain {domain} is already registered")

        # If no handler given then prevent every reloading
        if handler:
            self.registered_handlers[domain] = handler
        self.domain_reloadable[domain] = allow_reload
        if schema:
            self.domain_schemas[domain] = schema

        return await self.approve_domain_config(
            domain, self.cfg.get(domain, default), initial=True)
