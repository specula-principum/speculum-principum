"""Setup tools for repository configuration."""

from __future__ import annotations

import json
import shutil
import subprocess
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Mapping

from src.orchestration.tools import ToolDefinition, ToolRegistry, ActionRisk

def validate_url(args: Mapping[str, Any]) -> dict[str, Any]:
    url = args.get("url")
    if not url:
        return {"valid": False, "error": "URL is required"}
    
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            return {"valid": True, "url": url}
        else:
            return {"valid": False, "error": "Invalid URL format"}
    except Exception as e:
        return {"valid": False, "error": str(e)}

def configure_repository(args: Mapping[str, Any]) -> dict[str, Any]:
    source_url = args.get("source_url")
    topic = args.get("topic")
    frequency = args.get("frequency")
    
    config = {
        "source_url": source_url,
        "topic": topic,
        "frequency": frequency
    }
    
    config_path = Path("config/manifest.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    return {"success": True, "path": str(config_path)}

def clean_workspace(_: Mapping[str, Any]) -> dict[str, Any]:
    """Clean up workspace directories, preserving .gitkeep."""
    from src import paths
    
    directories = [
        paths.get_evidence_root(),
        paths.get_knowledge_graph_root(),
        paths.get_reports_root(),
    ]
    cleaned = []
    
    for dir_path in directories:
        if not dir_path.exists():
            continue

        # Safety check: Prevent accidental deletion of dev data
        if "dev_data" in str(dir_path.resolve()):
            print(f"Skipping cleanup of dev data directory: {dir_path}")
            continue
            
        for item in dir_path.iterdir():
            if item.name == ".gitkeep":
                continue
            
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        cleaned.append(str(dir_path))
        
    return {"success": True, "cleaned": cleaned}

def commit_and_push(args: Mapping[str, Any]) -> dict[str, Any]:
    branch = args.get("branch", "setup-config")
    message = args.get("message", "Setup repository configuration")
    
    try:
        # Configure git
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        
        # Create branch
        subprocess.run(["git", "checkout", "-b", branch], check=True)
        
        # Add changes
        subprocess.run(["git", "add", "."], check=True)
        
        # Commit
        subprocess.run(["git", "commit", "-m", message], check=True)
        
        # Push
        subprocess.run(["git", "push", "origin", branch], check=True)
        
        return {"success": True, "branch": branch}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}

def register_setup_tools(registry: ToolRegistry) -> None:
    registry.register_tool(
        ToolDefinition(
            name="validate_url",
            description="Validate a source URL.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to validate"}
                },
                "required": ["url"],
            },
            handler=validate_url,
            risk_level=ActionRisk.SAFE
        )
    )
    registry.register_tool(
        ToolDefinition(
            name="configure_repository",
            description="Generate the repository configuration file.",
            parameters={
                "type": "object",
                "properties": {
                    "source_url": {"type": "string"},
                    "topic": {"type": "string"},
                    "frequency": {"type": "string"}
                },
                "required": ["source_url", "topic", "frequency"],
            },
            handler=configure_repository,
            risk_level=ActionRisk.SAFE
        )
    )
    registry.register_tool(
        ToolDefinition(
            name="clean_workspace",
            description="Clean up workspace directories (evidence, knowledge-graph, reports), preserving .gitkeep.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=clean_workspace,
            risk_level=ActionRisk.DESTRUCTIVE
        )
    )
    registry.register_tool(
        ToolDefinition(
            name="commit_and_push",
            description="Commit local changes and push to a new branch.",
            parameters={
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "Branch name to create and push to."},
                    "message": {"type": "string", "description": "Commit message."}
                },
                "required": ["branch", "message"],
            },
            handler=commit_and_push,
            risk_level=ActionRisk.DESTRUCTIVE
        )
    )
