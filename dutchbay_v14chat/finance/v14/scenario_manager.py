"""Scenario Manager V14"""
from __future__ import annotations
import yaml, logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger(__name__)

class ScenarioManagerV14:
    """Manage tax scenarios"""
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        with open(self.config_path) as f:
            self.full_config = yaml.safe_load(f)
        self.base_config = deepcopy(self.full_config)
        if 'scenarios' not in self.full_config:
            raise ValueError("No scenarios in config")
        self.scenarios = self.full_config['scenarios']
    
    def list_scenarios(self):
        return list(self.scenarios.keys())
    
    def apply_scenario(self, name):
        config = deepcopy(self.base_config)
        config['_active_scenario'] = name
        if 'tax' in self.scenarios[name]:
            for k, v in self.scenarios[name]['tax'].items():
                config['tax'][k] = v
        return config
