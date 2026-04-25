const nextJest = require("next/jest")

const createJestConfig = nextJest({
  dir: "./"
})

const customJestConfig = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testMatch: ["<rootDir>/tests/unit/**/*.test.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1"
  }
}

module.exports = createJestConfig(customJestConfig)
