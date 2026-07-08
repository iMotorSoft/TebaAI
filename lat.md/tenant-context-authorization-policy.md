# TebaAI Tenant Context and Authorization Policy

This policy defines how organizations, workspaces, projects and knowledge scopes become enforceable backend context rather than passive schema metadata.

## Hierarchy

TebaAI uses a fixed ownership chain for product and knowledge resources.

```text
organization -> workspace -> project -> knowledge_scope -> document -> chunk
```

The presence of these foreign keys does not by itself implement isolation. Repositories and routes must enforce the chain.

## Effective Context

Every private request that accesses tenant-owned resources resolves an effective server-side context.

```text
authenticated_user_id
organization_id
workspace_id
project_id when applicable
knowledge_scope_id when applicable
effective_role and permissions
```

The backend derives this context from authenticated membership and resource ownership. Identifiers supplied by the browser are selectors to validate, not trusted authorization claims.

## Authorization Order

Authorization is resolved before data retrieval or mutation.

1. Validate the authenticated session and active user.
2. Load active membership for the requested organization, workspace and project.
3. Compute effective permissions from the narrowest applicable context.
4. Validate that the target resource belongs to that context.
5. Execute a repository operation already constrained by tenant and resource identity.

Returning an empty result is not a substitute for authorization when the caller lacks access.

## Repository Rule

Tenant-owned repository methods accept an explicit context or explicit tenant keys and constrain SQL in the same query that reads or mutates the resource.

Avoid load-then-check patterns when a scoped query can enforce ownership atomically. SQL stays in repositories under [[postgres-driver-policy]].

Duplicated organization, workspace and project fields on derived records must match the authoritative parent chain. They are denormalized filters, not independent ownership sources.

## Role and Permission Rule

The existing `admin`, `editor` and `viewer` roles are coarse application roles, not a complete multi-tenant permission model.

Before exposing multiple organizations or workspaces, define atomic permissions, membership precedence and administrative delegation in an ADR and migration. UI visibility never replaces backend permission checks.

## Scope Isolation

Knowledge access adds `knowledge_scope_id` and lifecycle constraints to tenant authorization.

Every lexical, vector, hybrid, generative and administrative knowledge flow follows [[knowledge-scope-contract]]. Cross-scope retrieval is forbidden unless an explicit shared scope and access policy are approved.

## Frontend Boundary

The frontend displays active context and may hide unavailable navigation, but it is not an authorization authority.

Changing workspace, project or scope invalidates stale page state, cached results and in-flight responses from the previous context.

## Audit

Security-relevant mutations and administrative context changes require attributable evidence.

Audit data should include actor, effective tenant context, action, resource, outcome, timestamp and correlation identifier without recording credentials or raw tokens.

## Current Gap

The product schema contains organizations, workspaces, projects, memberships and scope foreign keys. Library search now resolves the complete active membership chain before retrieval.

Migration 012 must be applied before activating the updated route against a real database. Other future multi-tenant surfaces remain disabled until their dependencies, repositories, negative tests and audit behavior implement this policy.

## Validation

Isolation requires positive and negative tests at repository and HTTP boundaries.

At minimum, verify allowed access, sibling-tenant denial, forged identifier denial, inactive membership denial, scope mismatch denial and stale frontend-context handling.
