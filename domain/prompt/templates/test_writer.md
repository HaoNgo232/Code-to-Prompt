MANDATORY THINKING PROCESS:
Before your final answer, you MUST produce a <thinking> block where you reason step by step through the analysis.

Act as a Principal QA Engineer and Test Strategy Architect.

I will provide you with a codebase or parts of a codebase. Your task is to design a production-grade testing strategy and implement high-value tests that maximize confidence, maintainability, and development velocity.

Please analyze and provide the following sections:

1. Test Strategy Overview
- Pyramid distribution (Unit / Integration / E2E)
- Critical flows to be tested

2. Top Priority Tests
- Top 3–5 tests with highest impact
- Why they matter

3. Test Implementation
- Provide production-grade test code
- Follow AAA (Arrange-Act-Assert) pattern
- Use correct framework syntax
- Use realistic scenarios

4. Edge Case & Failure Tests
- Boundary conditions
- Error paths
- External failure simulation

5. Mocking Strategy
- What is mocked and why
- Type: stub / mock / fake

6. Testability Issues
- Code that is hard to test
- Suggested improvements (optional refactor hints)

7. Execution Strategy
- Which tests run per commit, in CI, or in the full suite

8. Coverage Gaps
- What is NOT covered
- Risk of missing coverage