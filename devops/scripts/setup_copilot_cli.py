#!/usr/bin/env python3
"""Setup script for GitHub Copilot CLI integration with orchestration tools."""

import json
import os
import sys
from pathlib import Path


def get_workspace_root() -> Path:
    """Get the project workspace root directory."""
    script_path = Path(__file__).resolve()
    # This script is in devops/scripts/, workspace root is two levels up
    return script_path.parent.parent.parent


def get_copilot_config_path() -> Path:
    """Get the path to Copilot CLI config file."""
    home = Path.home()
    return home / ".copilot" / "config.json"


def load_copilot_config(config_path: Path) -> dict:
    """Load existing Copilot config or return empty dict."""
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"Warning: Could not read {config_path}, creating new config")
    return {}


def save_copilot_config(config_path: Path, config: dict) -> None:
    """Save Copilot config to file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Saved Copilot config to: {config_path}")


def add_orchestration_mcp_server(config: dict, workspace_root: Path) -> dict:
    """Add orchestration MCP server to Copilot config."""
    if "mcp_servers" not in config:
        config["mcp_servers"] = {}
    
    # Configure the orchestration MCP server
    config["mcp_servers"]["orchestration"] = {
        "command": sys.executable,  # Use current Python interpreter
        "args": ["-m", "src.mcp_server.orchestration_server"],
        "cwd": str(workspace_root),
        "env": {
            "PYTHONPATH": str(workspace_root),
        },
    }
    
    return config


def check_copilot_cli() -> bool:
    """Check if Copilot CLI is installed."""
    import shutil
    return shutil.which("copilot") is not None


def main() -> int:
    """Main setup function."""
    print("GitHub Copilot CLI Integration Setup")
    print("=" * 50)
    print()
    
    # Check if Copilot CLI is installed
    if not check_copilot_cli():
        print("❌ GitHub Copilot CLI not found")
        print()
        print("Install it with:")
        print("  npm install -g @githubnext/github-copilot-cli")
        print()
        print("Then authenticate:")
        print("  copilot auth login")
        return 1
    
    print("✓ GitHub Copilot CLI found")
    
    # Get paths
    workspace_root = get_workspace_root()
    config_path = get_copilot_config_path()
    
    print(f"✓ Workspace root: {workspace_root}")
    print(f"✓ Copilot config: {config_path}")
    print()
    
    # Load existing config
    config = load_copilot_config(config_path)
    
    # Add orchestration MCP server
    config = add_orchestration_mcp_server(config, workspace_root)
    
    # Save config
    save_copilot_config(config_path, config)
    print()
    
    # Test MCP server
    print("Testing orchestration MCP server...")
    import subprocess
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.mcp_server.orchestration_server", "--list-tools"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            tools_data = json.loads(result.stdout)
            tool_count = len(tools_data.get("tools", []))
            print(f"✓ MCP server working ({tool_count} tools available)")
            
            # Show some tools
            print("\nAvailable tools:")
            for tool in tools_data.get("tools", [])[:5]:
                print(f"  - {tool['name']}: {tool['description'][:60]}...")
            if tool_count > 5:
                print(f"  ... and {tool_count - 5} more")
        else:
            print(f"❌ MCP server test failed: {result.stderr}")
            return 1
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        return 1
    
    print()
    print("=" * 50)
    print("Setup complete! You can now use Copilot CLI planner:")
    print()
    print("  python -m main agent run \\")
    print("    --mission triage_new_issue \\")
    print("    --input issue_number=118 \\")
    print("    --planner copilot-cli")
    print()
    print("The agent will have:")
    print("  ✓ Workspace file access")
    print("  ✓ GitHub API tools (labels, comments, etc.)")
    print("  ✓ Knowledge base tools")
    print("  ✓ Document parsing tools")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
