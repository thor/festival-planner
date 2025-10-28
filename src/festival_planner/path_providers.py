"""Path provider implementations following XDG Base Directory specification.

This module provides abstractions for locating configuration and data directories,
following SOLID principles for extensibility and testability.

References:
    XDG Base Directory Specification:
    https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class PathProvider(ABC):
    """Abstract base class for path resolution strategies.
    
    Follows the Dependency Inversion Principle - depend on abstractions, not concretions.
    Follows the Interface Segregation Principle - focused interface for path operations.
    """

    @abstractmethod
    def get_config_home(self) -> Path:
        """Get the primary configuration directory for writing.
        
        Returns:
            Path to the writable configuration directory
        """
        pass

    @abstractmethod
    def get_config_dirs(self) -> list[Path]:
        """Get all configuration directories in search order.
        
        Returns:
            List of paths to search for configuration files, ordered by priority
        """
        pass

    @abstractmethod
    def get_data_home(self) -> Path:
        """Get the primary data directory for writing.
        
        Returns:
            Path to the writable data directory
        """
        pass

    @abstractmethod
    def get_data_dirs(self) -> list[Path]:
        """Get all data directories in search order.
        
        Returns:
            List of paths to search for data files, ordered by priority
        """
        pass

    @abstractmethod
    def get_state_home(self) -> Path:
        """Get the state directory for user-specific state data.
        
        Returns:
            Path to the state directory
        """
        pass

    @abstractmethod
    def get_cache_home(self) -> Path:
        """Get the cache directory for non-essential cached data.
        
        Returns:
            Path to the cache directory
        """
        pass


class XDGPathProvider(PathProvider):
    """XDG Base Directory specification compliant path provider.
    
    Implements the XDG Base Directory specification for locating configuration,
    data, state, and cache directories. Respects environment variables and provides
    sensible defaults.
    
    Follows the Single Responsibility Principle - focused on XDG path resolution.
    Follows the Open/Closed Principle - can be extended without modification.
    
    Args:
        app_name: Application name to append to XDG base directories
    
    Example:
        >>> provider = XDGPathProvider("festival-planner")
        >>> config_dir = provider.get_config_home()
        >>> # Returns: ~/.config/festival-planner
    """

    def __init__(self, app_name: str = "festival-planner"):
        """Initialize XDG path provider.
        
        Args:
            app_name: Application name for directory namespacing
        """
        self.app_name = app_name

    def get_config_home(self) -> Path:
        """Get XDG_CONFIG_HOME/app_name directory.
        
        Returns:
            Path to user configuration directory (default: ~/.config/festival-planner)
        """
        base = os.environ.get("XDG_CONFIG_HOME")
        if base:
            return Path(base) / self.app_name
        return Path.home() / ".config" / self.app_name

    def get_config_dirs(self) -> list[Path]:
        """Get configuration directories in search order.
        
        Search order:
        1. XDG_CONFIG_HOME/app_name
        2. Each directory in XDG_CONFIG_DIRS/app_name (left to right)
        3. ./config (current working directory fallback for compatibility)
        
        Returns:
            List of configuration directories to search
        """
        dirs = [self.get_config_home()]
        
        config_dirs_env = os.environ.get("XDG_CONFIG_DIRS")
        if config_dirs_env:
            for dir_str in config_dirs_env.split(":"):
                if dir_str.strip():
                    dirs.append(Path(dir_str) / self.app_name)
        else:
            # Default system-wide config directory
            dirs.append(Path("/etc/xdg") / self.app_name)
        
        # Add current working directory as final fallback for backward compatibility
        cwd_config = Path.cwd() / "config"
        if cwd_config not in dirs:
            dirs.append(cwd_config)
        
        return dirs

    def get_data_home(self) -> Path:
        """Get XDG_DATA_HOME/app_name directory.
        
        Returns:
            Path to user data directory (default: ~/.local/share/festival-planner)
        """
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base) / self.app_name
        return Path.home() / ".local" / "share" / self.app_name

    def get_data_dirs(self) -> list[Path]:
        """Get data directories in search order.
        
        Search order:
        1. XDG_DATA_HOME/app_name
        2. Each directory in XDG_DATA_DIRS/app_name (left to right)
        3. ./data (current working directory fallback for compatibility)
        
        Returns:
            List of data directories to search
        """
        dirs = [self.get_data_home()]
        
        data_dirs_env = os.environ.get("XDG_DATA_DIRS")
        if data_dirs_env:
            for dir_str in data_dirs_env.split(":"):
                if dir_str.strip():
                    dirs.append(Path(dir_str) / self.app_name)
        else:
            # Default system-wide data directories
            dirs.extend([
                Path("/usr/local/share") / self.app_name,
                Path("/usr/share") / self.app_name,
            ])
        
        # Add current working directory as final fallback for backward compatibility
        cwd_data = Path.cwd() / "data"
        if cwd_data not in dirs:
            dirs.append(cwd_data)
        
        return dirs

    def get_state_home(self) -> Path:
        """Get XDG_STATE_HOME/app_name directory.
        
        Returns:
            Path to state directory (default: ~/.local/state/festival-planner)
        """
        base = os.environ.get("XDG_STATE_HOME")
        if base:
            return Path(base) / self.app_name
        return Path.home() / ".local" / "state" / self.app_name

    def get_cache_home(self) -> Path:
        """Get XDG_CACHE_HOME/app_name directory.
        
        Returns:
            Path to cache directory (default: ~/.cache/festival-planner)
        """
        base = os.environ.get("XDG_CACHE_HOME")
        if base:
            return Path(base) / self.app_name
        return Path.home() / ".cache" / self.app_name


def create_default_path_provider() -> PathProvider:
    """Create the default XDG-compliant path provider.
    
    Returns:
        XDGPathProvider instance configured for festival-planner
    
    Example:
        >>> provider = create_default_path_provider()
        >>> config_dir = provider.get_config_home()
        >>> # Returns: ~/.config/festival-planner
    """
    return XDGPathProvider()
