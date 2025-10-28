# XDG Base Directory Implementation

This document describes the XDG Base Directory specification implementation in the festival-planner application.

## Overview

The application now follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) for organizing configuration and data files, while maintaining backward compatibility with existing `./config` and `./data` directories.

## Architecture

The implementation follows SOLID principles with a clean separation of concerns:

### PathProvider Abstraction

**Location**: `src/festival_planner/path_providers.py`

- **`PathProvider`** (Abstract Base Class): Defines the interface for path resolution
- **`XDGPathProvider`**: Implements XDG Base Directory specification
- **`create_default_path_provider()`**: Factory function for creating providers

### ConfigLoader Integration

**Location**: `src/festival_planner/config.py`

The `ConfigLoader` class has been updated to:
1. Accept a `PathProvider` for dependency injection
2. Search multiple directories in priority order for reading
3. Always write to the primary (XDG home) directories
4. Maintain backward compatibility with explicit `config_dir`/`data_dir` parameters

## Directory Layout

### XDG-Compliant Directories

#### Configuration Files
**Primary (write)**: `$XDG_CONFIG_HOME/festival-planner` (default: `~/.config/festival-planner`)

**Search paths (in order)**:
1. `$XDG_CONFIG_HOME/festival-planner`
2. Each directory in `$XDG_CONFIG_DIRS/festival-planner` (e.g., `/etc/xdg/festival-planner`)
3. `./config` (backward compatibility fallback)

**Files**:
- `config.yaml` - User configuration (cinemas, schedule preferences, priorities)
- `preferences.yaml` - Tool-maintained preferences (seen films, weight overrides)

#### Data Files
**Primary (write)**: `$XDG_DATA_HOME/festival-planner` (default: `~/.local/share/festival-planner`)

**Search paths (in order)**:
1. `$XDG_DATA_HOME/festival-planner`
2. Each directory in `$XDG_DATA_DIRS/festival-planner` (e.g., `/usr/local/share/festival-planner`, `/usr/share/festival-planner`)
3. `./data` (backward compatibility fallback)

**Files**:
- `films.yaml` - Scraped festival programme data

#### Cache Files
**Location**: `$XDG_CACHE_HOME/festival-planner` (default: `~/.cache/festival-planner`)

**Purpose**: HTTP cache and other non-essential cached data

#### State Files
**Location**: `$XDG_STATE_HOME/festival-planner` (default: `~/.local/state/festival-planner`)

**Purpose**: Application state data (reserved for future use)

## Search Order and Fallback

### Reading Files
The application searches for files in multiple directories (listed above) in priority order and uses the first match found. This allows:
- User-specific overrides in `~/.config/festival-planner`
- System-wide defaults in `/etc/xdg/festival-planner`
- Project-local files in `./config` (for development/testing)

### Writing Files
All writes go to the primary directories:
- Configuration: `$XDG_CONFIG_HOME/festival-planner`
- Data: `$XDG_DATA_HOME/festival-planner`
- Cache: `$XDG_CACHE_HOME/festival-planner`

This ensures user data is always stored in standard, user-writable locations.

## Environment Variables

The implementation respects standard XDG environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `XDG_CONFIG_HOME` | Base directory for user configuration files | `~/.config` |
| `XDG_CONFIG_DIRS` | Colon-separated list of system config directories | `/etc/xdg` |
| `XDG_DATA_HOME` | Base directory for user data files | `~/.local/share` |
| `XDG_DATA_DIRS` | Colon-separated list of system data directories | `/usr/local/share:/usr/share` |
| `XDG_CACHE_HOME` | Base directory for user cache files | `~/.cache` |
| `XDG_STATE_HOME` | Base directory for user state files | `~/.local/state` |

## SOLID Principles

The implementation adheres to SOLID principles:

1. **Single Responsibility Principle (SRP)**
   - `PathProvider`: Resolves directory paths
   - `ConfigLoader`: Handles configuration I/O
   - Each has a focused, well-defined responsibility

2. **Open/Closed Principle (OCP)**
   - `PathProvider` can be extended without modifying `ConfigLoader`
   - New path providers can be added by implementing the `PathProvider` interface

3. **Liskov Substitution Principle (LSP)**
   - Any `PathProvider` implementation can be substituted for another
   - `ConfigLoader` works with any `PathProvider`

4. **Interface Segregation Principle (ISP)**
   - `PathProvider` has a focused interface for path operations
   - Clients only depend on the methods they use

5. **Dependency Inversion Principle (DIP)**
   - `ConfigLoader` depends on the `PathProvider` abstraction, not concrete implementations
   - High-level modules don't depend on low-level modules

## Migration Path

### For Existing Users

No action required! The application will:
1. Check XDG directories first
2. Fall back to `./config` and `./data` automatically
3. Continue to work with existing setups

### Recommended Migration

To adopt XDG standards:

```bash
# Create XDG directories
mkdir -p ~/.config/festival-planner
mkdir -p ~/.local/share/festival-planner

# Move configuration files
mv ./config/config.yaml ~/.config/festival-planner/
mv ./config/preferences.yaml ~/.config/festival-planner/

# Move data files
mv ./data/films.yaml ~/.local/share/festival-planner/

# The application will now use XDG directories
```

### For System-Wide Installations

System administrators can place default configuration in:
- `/etc/xdg/festival-planner/config.yaml`

Users can override with personal files in:
- `~/.config/festival-planner/config.yaml`

## Usage Examples

### Default Usage (XDG-compliant)

```python
from festival_planner.config import ConfigLoader

# Uses XDG paths with fallback to ./config and ./data
loader = ConfigLoader()
config = loader.load_config()  # Searches all directories
loader.save_preferences(prefs)  # Writes to XDG_CONFIG_HOME
```

### Custom Path Provider

```python
from festival_planner.config import ConfigLoader
from festival_planner.path_providers import XDGPathProvider

# Custom provider with different app name
provider = XDGPathProvider("my-custom-festival")
loader = ConfigLoader(path_provider=provider)
```

### Backward Compatibility

```python
from pathlib import Path
from festival_planner.config import ConfigLoader

# Explicit directories (disables XDG search)
loader = ConfigLoader(
    config_dir=Path("./config"),
    data_dir=Path("./data")
)
```

## Testing

The implementation has been validated to:
1. ✅ Load configuration from `./config` (fallback)
2. ✅ Load data from `./data` (fallback)
3. ✅ Use correct XDG directory paths
4. ✅ Maintain search order priority
5. ✅ Write to XDG home directories
6. ✅ Maintain backward compatibility with explicit paths

## Benefits

1. **Standards Compliance**: Follows established Unix/Linux conventions
2. **User-Friendly**: Config files in predictable, standard locations
3. **Multi-User Support**: Clean separation of user and system-wide configs
4. **Portable**: Works across different environments
5. **Testable**: Easy to inject mock providers for testing
6. **Backward Compatible**: Existing setups continue to work
7. **Extensible**: New path providers can be added easily

## Future Enhancements

Potential future improvements:
- Windows-specific path provider (using `%APPDATA%`, `%LOCALAPPDATA%`)
- macOS-specific path provider (using `~/Library/Application Support`)
- Runtime configuration file hot-reloading
- Config file validation and migration tools
