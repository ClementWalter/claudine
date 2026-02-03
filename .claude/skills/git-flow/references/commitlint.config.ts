import type { UserConfig } from "@commitlint/types";

/**
 * Commitlint configuration for Zama repositories.
 *
 * Enforces conventional commits with Zama-specific types and scopes.
 * Used by both commit messages and PR titles.
 */
const Configuration: UserConfig = {
  extends: ["@commitlint/config-conventional"],
  parserPreset: "conventional-changelog-conventionalcommits",

  rules: {
    // Type is required and must be one of these values
    "type-empty": [2, "never"],
    "type-enum": [
      2,
      "always",
      [
        "ci",
        "chore",
        "docs",
        "ticket",
        "feat",
        "fix",
        "perf",
        "refactor",
        "revert",
        "style",
        "test",
      ],
    ],

    // Scope must be one of these values when provided
    "scope-enum": [
      2,
      "always",
      [
        "coprocessor",
        "host-contracts",
        "gateway-contracts",
        "contracts",
        "library-solidity",
        "kms-connector",
        "sdk",
        "test-suite",
        "charts",
        "common",
      ],
    ],
  },
};

export default Configuration;
