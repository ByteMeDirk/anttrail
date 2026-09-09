# AntTrail

AntTrail is a lightweight Python library for building structured, queryable repository graphs. It helps agents and other
software systems retrieve object context without reading or scraping an entire repository.

AntTrail represents repository artefacts and their relationships as a graph.

The result is a concise, navigable “ant trail” through a repository: a machine-readable map that helps downstream
systems identify relevant artefacts and understand how they relate.

To run AntTrail, set up `uv` first. Then you can call `anttrail` like this:

```shell
uv run anttrail --directory "<directory>" -sschema-version "v1.0" --validate true --output "<file.ext>"
```

Better documentation will be added on the first official release.

## Current capabilities

AntTrail currently:

- Traverses a configured repository or directory root.
- Creates graph nodes for directories and files.
- Creates directed `CONTAINS` relationships for immediate parent-child filesystem relationships.
- Uses normalized root-relative IDs for stable graph traversal.
- Validates containment relationships, node references, root reachability, and weak graph connectivity.
- Exports a structured graph model and a Cypher-like diagnostic representation.

At present, AntTrail models filesystem structure. It does not yet extract semantic document content.

## Motivation

Large repositories are expensive for agents read through. Loading an entire repo into an agent context window can be
ineffective and costly.

The project was motivated by two related use cases:

1. **Agent-oriented repository navigation**  
   Build an explainable repository map that supports targeted context retrieval, navigation, and dependency-aware
   traversal without overloading an agent’s context window.
2. **Dynamic ontology generation from multimodal sources**  
   Build structural and semantic graphs from repository and document artefacts that can later support ontology
   generation, classification, metadata extraction, and relationship discovery.

## Planned direction

**Note**: this is not supposed to be another Graph database or query engine...

Future versions may support:

- Extended relationship functionality.
- Object parsing, such as modules, classes, functions, imports, etc. if the object is a `.py` file.
- NLP-based metadata and entity extraction from non-standard objects.
- OCR-based metadata extraction from images and documents.
- Graph querying, filtering, and traversal (limited).
- Dreaming big here: export to JSON, graph databases, GraphML, DOT, and Cypher-compatible formats.

AntTrail is intended to remain lightweight and deterministic, so I will not be incorporating an LLM to do the heavy
lifting. I want it to be local-first, lightweight, deterministic, extensible, and agent-friendly.

---

Please note that this is currently a project in its infancy. Part of this endeavor is to produce something original
and challenging. Therefore, **no agent co-authoring/coding** is used in this repository. Subject material in question is
sourced from an LLM or the web, but the code in this repo is made by a human, and the goal is to keep it that way.

> It's gonna be ugly at first, but hopefully it gets better :D