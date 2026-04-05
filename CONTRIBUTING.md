# Contributing to evo-skills

## Commit Convention

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <description>

<body>

<footer>
```

### Types

| Type | Description |
|------|------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes |
| `chore` | Maintenance tasks (deps, configs) |
| `refactor` | Code restructuring without behavior change |
| `test` | Adding or updating tests |
| `ci` | CI/CD changes |
| `perf` | Performance improvements |
| `style` | Code style (formatting, no logic change) |
| `build` | Build system changes |

### Scope (optional)

- `scheduler` — scheduler service
- `client` — evo-skills-client CLI
- `skill` — skill definitions
- `docs` — documentation

### Examples

```
feat(scheduler): add hot-reload for yaml configs

docs: add project motivation to README

fix(client): handle missing state.json gracefully

chore: update .gitignore for open source release
```

### Breaking Changes

Append `!` after type/scope:

```
feat(scheduler)!: change config format from JSON to YAML
```
