import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ADMIN_ROLE_ID,
  ensureAdminRole,
  isAdminRoleId,
  rbacDirty,
  removeRoleAt,
  upsertRole,
} from "../../../src/features/rbac/rbacDocument.ts";

const WILDCARD_READ = "*:read";
const WILDCARD_WRITE = "*:write";

describe("rbacDocument", () => {
  it("ensureAdminRole locks admin wildcards first", () => {
    const doc = ensureAdminRole({
      version: 1,
      roles: [
        { id: "viewer", permissions: ["status:read"] },
        { id: "Admin", permissions: ["logs:read"] },
      ],
      bindings: [],
    });
    assert.equal(doc.roles[0]?.id, ADMIN_ROLE_ID);
    assert.deepEqual(doc.roles[0]?.permissions, [WILDCARD_READ, WILDCARD_WRITE]);
    assert.equal(doc.roles.length, 2);
    assert.equal(doc.roles[1]?.id, "viewer");
  });

  it("refuses deleting the builtin admin role", () => {
    const roles = ensureAdminRole({
      version: 1,
      roles: [{ id: "viewer", permissions: [] }],
      bindings: [],
    }).roles;
    assert.equal(removeRoleAt(roles, 0), roles);
    assert.equal(removeRoleAt(roles, 1).length, 1);
    assert.equal(isAdminRoleId("ADMIN"), true);
  });

  it("upsertRole updates custom roles only", () => {
    const roles = [
      { id: ADMIN_ROLE_ID, permissions: [WILDCARD_READ, WILDCARD_WRITE] },
      { id: "viewer", permissions: ["status:read"] },
    ];
    const next = upsertRole(
      roles,
      { id: "viewer", permissions: ["status:read", "logs:read"] },
      1,
    );
    assert.deepEqual(next[1]?.permissions, ["status:read", "logs:read"]);
    assert.deepEqual(
      upsertRole(roles, { id: "hacked", permissions: [] }, 0),
      roles,
    );
  });

  it("rbacDirty compares form and yaml baselines", () => {
    const draft = {
      version: 1,
      roles: [{ id: ADMIN_ROLE_ID, permissions: [WILDCARD_READ, WILDCARD_WRITE] }],
      bindings: [],
    };
    const savedJson = JSON.stringify(draft);
    assert.equal(
      rbacDirty({
        mode: "form",
        draft,
        savedJson,
        yamlText: "",
        yamlBaseline: "",
      }),
      false,
    );
    assert.equal(
      rbacDirty({
        mode: "yaml",
        draft,
        savedJson,
        yamlText: "version: 1\n",
        yamlBaseline: "version: 1\n",
      }),
      false,
    );
    assert.equal(
      rbacDirty({
        mode: "yaml",
        draft,
        savedJson,
        yamlText: "version: 2\n",
        yamlBaseline: "version: 1\n",
      }),
      true,
    );
  });
});
