MANDATORY THINKING PROCESS:
Before your final answer, you MUST produce a <thinking> block where you reason step by step through the analysis.

Act as a Senior Developer Advocate and Technical Writer.

I will provide you with a codebase or parts of a codebase. Your task is to produce developer documentation that is fast to understand, easy to start, deep enough for real usage, and grounded in the actual codebase (no generic templates).

Please generate a README.md containing the following sections:

1. TL;DR
- What it does: 1–2 line value proposition
- Who it's for: target users
- Why use it: main advantage

2. Quick Start (≤10 minutes)
- Prerequisites: Required runtimes, tools, versions
- Installation: Real commands based on the project
- Run: How to start the app / service / CLI
- Verify it works: Expected output / endpoint / UI

3. Core Concepts
Explain only the essential mental model:
- Key components
- How they interact
- What the user must understand to use the system

4. Key Modules / Components
For each important module, provide:
- Name
- Purpose
- File path
- How it connects to others

5. Configuration
- Environment variables
- Config files
- External dependencies (DB, APIs, services)

6. Usage Examples
Provide real examples from code:
- Realistic usage example code snippet
- Explain what the example does
- Show expected result

7. Development (only if relevant)
- How to run locally
- Test commands
- Lint / format (if exists)

8. Troubleshooting
List only real issues detectable from code:
- Common errors
- Misconfigurations
- Dependency issues

9. When NOT to use this
- Anti-use cases
- Limitations
- Known constraints

10. Next Steps (optional)
- Advanced usage
- Scaling notes
- Contribution guide (if needed)