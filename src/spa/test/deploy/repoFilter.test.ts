import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  filterGithubRepos,
  type GithubRepo,
} from "../../src/deploy/githubApi.ts";

function repo(fullName: string): GithubRepo {
  const [owner, name] = fullName.split("/", 2);
  return {
    full_name: fullName,
    name: name || fullName,
    owner: owner || "",
    private: false,
    default_branch: "main",
    html_url: `https://github.com/${fullName}`,
  };
}

describe("filterGithubRepos", () => {
  const repos = [
    repo("demo-org/demo-api"),
    repo("demo-org/other"),
    repo("demo-user/http-only-site"),
  ];

  it("returns all repos when query is empty", () => {
    assert.equal(filterGithubRepos(repos, "").length, 3);
    assert.equal(filterGithubRepos(repos, "   ").length, 3);
  });

  it("filters by owner or name substring", () => {
    assert.deepEqual(
      filterGithubRepos(repos, "demo-api").map((r) => r.full_name),
      ["demo-org/demo-api"],
    );
    assert.deepEqual(
      filterGithubRepos(repos, "DEMO-ORG").map((r) => r.full_name),
      ["demo-org/demo-api", "demo-org/other"],
    );
  });

  it("returns empty when nothing matches", () => {
    assert.deepEqual(filterGithubRepos(repos, "nope"), []);
  });
});
