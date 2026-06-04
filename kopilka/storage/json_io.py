"""Load and save budget JSON files."""

import json
import os
from pathlib import Path
from kopilka.model.budget import Budget


def ensure_config_dir():
    """Ensure config directory exists."""
    config_dir = Path.home() / ".config" / "kopilka"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_budget_path() -> str:
    """Get the budget file path."""
    # First check for user-configured path
    config_file = Path.home() / ".config" / "kopilka" / "config.json"
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                if 'budget_path' in config:
                    return config['budget_path']
        except:
            pass
    
    # Default to ~/.config/kopilka/budget.json
    return str(Path.home() / ".config" / "kopilka" / "budget.json")


def load_budget() -> Budget:
    """Load budget from JSON file."""
    budget_path = get_budget_path()
    
    if os.path.exists(budget_path):
        try:
            with open(budget_path, 'r') as f:
                data = json.load(f)
                return Budget.from_dict(data)
        except Exception as e:
            print(f"Error loading budget: {e}")
            return Budget()
    
    # Create new budget if not found
    return Budget()


def save_budget(budget: Budget) -> bool:
    """Save budget to JSON file."""
    budget_path = get_budget_path()
    
    try:
        # Ensure directory exists
        Path(budget_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save to file
        with open(budget_path, 'w') as f:
            data = budget.to_dict()
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving budget: {e}")
        return False


def set_budget_path(path: str):
    """Set custom budget file path."""
    config_dir = ensure_config_dir()
    config_file = config_dir / "config.json"

    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)

    config['budget_path'] = path

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


def load_config() -> dict:
    """Load app config from ~/.config/kopilka/config.json."""
    config_file = Path.home() / ".config" / "kopilka" / "config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config: dict):
    """Save app config to ~/.config/kopilka/config.json."""
    config_dir = ensure_config_dir()
    with open(config_dir / "config.json", 'w') as f:
        json.dump(config, f, indent=2)


def is_first_launch() -> bool:
    """Return True if setup wizard has not been completed."""
    config = load_config()
    return "user1_name" not in config


