"""Extraction logic using GitHub Models."""

from __future__ import annotations

import json
from typing import List

from src.integrations.copilot import CopilotClient, CopilotClientError
from src.knowledge.storage import KnowledgeGraphStorage
from src.parsing.base import ParsedDocument
from src.parsing.storage import ManifestEntry, ParseStorage


class ExtractionError(RuntimeError):
    """Raised when extraction fails."""


class PersonExtractor:
    """Extracts person names from text using an LLM."""

    def __init__(self, client: CopilotClient) -> None:
        self.client = client

    def extract_people(self, text: str) -> List[str]:
        """Extract a list of person names from the provided text."""
        if not text.strip():
            return []

        system_prompt = (
            "You are an expert entity extractor. Your task is to extract all unique person names "
            "from the provided text. Return ONLY a JSON array of strings. "
            "Do not include titles (Mr., Dr.) unless necessary for disambiguation. "
            "Normalize names to 'First Last' format where possible. "
            "If no people are found, return an empty array []."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        try:
            response = self.client.chat_completion(
                messages=messages,
                temperature=0.1,  # Low temperature for deterministic output
                max_tokens=2000,
            )
        except CopilotClientError as exc:
            raise ExtractionError(f"LLM call failed: {exc}") from exc

        if not response.choices:
            raise ExtractionError("No response from LLM")

        content = response.choices[0].message.content or "[]"
        
        # Clean up potential markdown code blocks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        try:
            data = json.loads(content)
            if not isinstance(data, list):
                raise ExtractionError("LLM did not return a JSON array")
            return [str(name) for name in data if isinstance(name, (str, int, float))]
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"Failed to parse LLM response as JSON: {content}") from exc


def process_document(
    entry: ManifestEntry,
    storage: ParseStorage,
    kb_storage: KnowledgeGraphStorage,
    extractor: PersonExtractor,
) -> List[str]:
    """Process a parsed document to extract people and save to KB."""
    
    # Load the document content
    # We need to reconstruct the full text from the artifact
    # The artifact path in manifest is relative to storage root
    artifact_path = storage.root / entry.artifact_path
    
    if not artifact_path.exists():
        raise ExtractionError(f"Artifact not found: {artifact_path}")

    # If it's a directory (page-directory), read all pages
    # If it's a file, read it directly
    full_text = ""
    
    if artifact_path.is_dir():
        # It's a directory of pages
        # We should look for index.md to find the order, or just glob
        # For simplicity, let's glob *.md excluding index.md and sort
        pages = sorted([p for p in artifact_path.glob("*.md") if p.name != "index.md"])
        full_text = "\n\n".join([p.read_text(encoding="utf-8") for p in pages])
    else:
        # It's a single file
        full_text = artifact_path.read_text(encoding="utf-8")

    if not full_text.strip():
        return []

    # Extract people
    people = extractor.extract_people(full_text)

    # Save to KB
    kb_storage.save_extracted_people(entry.checksum, people)

    return people
