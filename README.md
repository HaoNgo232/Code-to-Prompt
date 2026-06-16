# Synapse Desktop

> **Manually select the right code context, use AI web chat to analyze or plan, then give your IDE agent a clearer task with less exploration cost.**

_Note: This is a personal tool built to reduce AI costs by using web chat for planning instead of expensive IDE agent scans._

**Synapse Desktop** is a local desktop app that helps you manually select project files, package them into AI-ready prompts, and use web chat models such as ChatGPT, Claude, or Gemini to understand code, create plans, or prepare specs before using an IDE agent.

The main goal is simple:

```text
Use cheaper / free AI web chat for context understanding and planning
→ reduce how much your paid IDE agent needs to spend exploring the codebase
```

IDE agents can already explore and understand codebases by themselves.  
But that exploration often costs time, tool calls, and tokens.

Synapse Desktop helps you front-load part of that work manually:

```text
You choose relevant files
→ Synapse Desktop packages them
→ Web chat analyzes / plans
→ IDE agent receives a clearer task
→ IDE agent spends less context discovering what you already prepared
```

![Context tab](assets/image.png)

---

## Installation

> Synapse Desktop is currently tested mainly on Linux.  
> Windows support is beta.  
> macOS has not been fully tested yet.

**Requirements:** Python 3.10+ · Git (optional, for Git Diff and branch detection)

Pick your usecase and copy the entire block:

---

### 🚀 Quick Start — Linux

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
chmod +x start.sh && ./start.sh
```

### 🚀 Quick Start — Windows

```powershell
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
.\start.bat
```

### 📦 Build AppImage — Linux

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
# Build standard version (enforces license check):
chmod +x build-appimage.sh && ./build-appimage.sh

# Build personal version (bypasses license check by default):
chmod +x build-appimage.sh && ./build-appimage.sh --no-license
```

### 📦 Build Windows .exe

```powershell
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
# Build standard version (enforces license check):
.\build-windows.ps1

# Build personal version (bypasses license check by default):
.\build-windows.ps1 -NoLicense
```

### 🔧 Manual Install — Linux / macOS

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main_window.py
```

### 🔧 Manual Install — Windows PowerShell

```powershell
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main_window.py
```

---

## What problem does Synapse Desktop solve?

AI coding agents inside IDEs are powerful. They can read files, search code, inspect dependencies, and understand the project by themselves.

But that process is not free.

When an IDE agent explores a codebase, it may spend:

- tokens reading files
- tool calls searching the repository
- time building context
- paid usage quota
- multiple back-and-forth turns before implementation even starts

For many tasks, you already know which files are likely relevant.

**Synapse Desktop lets you manually select those files first, package them into a structured prompt, and use AI web chat to analyze or plan before involving your IDE agent.**

This is useful when you want to:

- save Cursor / Claude Code / Cline / Windsurf quota
- reduce agent exploration cost
- use free or cheaper ChatGPT / Claude / Gemini web chat for planning
- control exactly which files are sent as context
- avoid sending the whole repository
- create a clearer task before asking the IDE agent to implement
- keep the IDE agent focused on execution instead of discovery

---

## Core workflow

```text
1. Open your project folder
2. Manually select relevant files
3. Add task instructions
4. Copy structured context
5. Paste into AI web chat
6. Ask the web chat to analyze, plan, or write a spec
7. Paste the result into your IDE agent
8. Let the agent implement with less exploration
```

This workflow does **not** replace IDE agents.

It helps you use them more efficiently.

```text
Web chat = cheaper planning / analysis layer
IDE agent = implementation layer
```

---

## Why use web chat before an IDE agent?

AI web chats are often cheaper or included in a subscription you already have.

For example, you may want to use:

- ChatGPT Web
- Claude Web
- Gemini Web
- DeepSeek Web
- other hosted chat models

These tools are good at:

- understanding selected code
- explaining architecture
- creating plans
- identifying relevant risks
- drafting implementation specs
- reviewing design options

Then your IDE agent can focus on:

- editing files
- running tests
- applying changes
- fixing errors
- iterating on implementation

This split can reduce paid IDE agent usage because the agent does not need to spend as much context discovering the same information.

---

## Important: manual selection is the main idea

Synapse Desktop is intentionally built around **manual file selection**.

The user remains in control.

You decide what files matter.  
You decide what context to send.  
You decide whether to include full code, compressed structure, git diff, or only the tree map.

This is different from asking an agent to explore everything automatically.

The value is not full automation.

The value is:

```text
human-guided context selection
→ cheaper AI planning
→ more focused IDE agent execution
```

---

## Workflows

Synapse Desktop supports multiple workflows — see [Example workflows](#example-workflows) below for step-by-step guides with copy-paste prompts.

## Key features

### Visual file selection

Open a project folder and select files from a tree view.

No need to manually open files one by one.

The token count updates in real time as you select or deselect files.

![Context tab](assets/image.png)

---

### Copy modes

| Mode                      | What it copies                                                                            | Best for                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **Copy Context**          | Full content of selected files                                                            | Web chat planning, debugging, code review, spec generation |
| **Compress**              | Code structure such as classes, functions, signatures, and parameters without full bodies | Architecture analysis and lower token usage                |
| **Git Diff**              | Current git changes only                                                                  | Reviewing recent edits                                     |
| **Copy Tree Map**         | Directory structure only                                                                  | Asking AI which files may be relevant                      |
| **Copy + Search/Replace** | Context plus patch-format instructions                                                    | Direct patch generation and Apply tab workflow             |

---

### Token counting

Synapse Desktop shows token usage while you select files.

This helps you avoid sending too much context to AI web chat.

It can break down token usage for:

- selected file content
- instructions
- tree map
- git diff
- overhead

---

### Tree map copy

Copy only the directory structure without file contents.

This is useful when you want to ask AI:

```text
Which files should I include for this task?
```

Example prompt:

```text
Here is the project tree.

Based on this task, suggest which files are most likely relevant.

Task:
[Describe task]

Return:
- prioritized file list
- short reason for each file
- what context I should provide next
```

---

### Related Files

Synapse Desktop can help include files related by imports or dependencies.

You can choose depth from 1 to 5.

This is helpful after you manually choose a starting file and want nearby supporting files.

Manual control still remains the main workflow.

---

### AI Suggest Select

You can provide a task description and ask AI to suggest relevant files.

This requires API key configuration in Settings.

This is optional.  
The main workflow does not require API keys.

---

### Context presets

Save selected files and instructions as presets.

Useful when repeatedly working on:

- one feature area
- one module
- one bug category
- one review workflow
- one recurring prompt

See: [docs/PRESETS.md](docs/PRESETS.md)

---

### Prompt templates

Synapse Desktop includes reusable prompt templates for common tasks:

- planning
- spec generation
- code review
- bug analysis
- refactoring plan
- test planning
- security audit
- Search/Replace patch generation

You can also create your own templates.

---

## Search/Replace patch application

When using **Copy + Search/Replace**, the AI can return patch blocks like this:

```text
<<<<<<< SEARCH src/app.py
print("hello")
=======
print("hello world")
>>>>>>> REPLACE
```

Then you can:

1. Copy the AI response.
2. Open the **Apply** tab.
3. Paste the response.
4. Click **Preview**.
5. Review visual diffs.
6. Apply changes safely.

![Apply tab](assets/image-1.png)

---

## Supported patch operations

### Modify a file

```text
<<<<<<< SEARCH path/to/file.ext
original code here
=======
replacement code here
>>>>>>> REPLACE
```

### Create a file

```text
<<<<<<< SEARCH path/to/new_file.ext
=======
new file content here
>>>>>>> REPLACE
```

### Delete a file

```text
<<<<<<< DELETE path/to/file.ext
>>>>>>> DELETE
```

### Rename or move a file

```text
<<<<<<< RENAME path/to/old_file.ext
=======
path/to/new_file.ext
>>>>>>> RENAME
```

---

## Visual diff preview

Before applying AI-generated changes, Synapse Desktop shows a diff preview.

This helps you catch mistakes before modifying your project.

Original files are backed up automatically before changes are applied.

---

## Copy Error Context

If an AI-generated patch cannot be applied because the search block does not match the current file, Synapse Desktop can generate error context.

Send that error context back to the AI so it can correct the patch.

---

## Security

### Local-first

Synapse Desktop processes your project locally.

Your code is not uploaded by Synapse Desktop.

You decide what to copy and where to paste it.

---

### Secret scanning

Before copying context, Synapse Desktop can scan for possible secrets such as:

- API keys
- access tokens
- passwords
- private credentials

If a secret-like value is found, the app shows a warning with a masked preview.

---

### Relative paths

You can enable relative paths to avoid exposing absolute local machine paths.

Example:

```text
/home/username/work/project/src/app.py
```

becomes:

```text
src/app.py
```

---

### Safety recommendations

Synapse Desktop can read and modify files in folders you open.

Before applying patches:

- use git
- commit your current work
- review the diff preview
- keep backups enabled
- avoid sending secrets to external AI providers
- prefer small patches over large patches

---

## MCP server for AI IDEs

Synapse Desktop can run as an MCP server for AI IDEs such as Cursor, Claude Code, and other MCP-compatible tools.

Currently, the MCP server provides:

```text
manage_selection
```

This allows an AI agent to select or deselect files in the workspace.

Other operations such as reading files, searching, git operations, and language intelligence are usually better handled by the IDE's built-in tools or LSP.

Configuration:

```text
Settings → MCP Server Integration → Install to IDE
```

---

## Interface

### Context tab

Select files, write instructions, choose copy mode, and prepare context.

![Context tab](assets/image.png)

---

### Apply tab

Paste Search/Replace blocks from AI, preview diffs, and apply changes.

![Apply tab](assets/image-1.png)

---

### History tab

Review copy and apply history.

![History tab](assets/image-2.png)

---

### Settings tab

Configure models, token counting, security options, MCP integration, and app behavior.

![Settings tab](assets/image-3.png)

---

## Example workflows

Each workflow includes steps and a copy-paste prompt.

---

### Workflow A: Web chat planning to save IDE agent cost

1. Select relevant files → **Copy Context**
2. Paste into ChatGPT / Claude / Gemini Web
3. Get analysis and implementation plan
4. Paste the plan into your IDE agent

**Prompt for web chat:**

```text
Analyze the selected code context and create a practical implementation plan.

Task:
[Describe task]

Do not write the full code.
Do not return a patch.

Focus on:
- what the current code does
- which files matter
- what needs to change
- implementation steps
- risks
- test plan
- acceptance criteria
```

**Prompt for IDE agent:**

```text
Implement this plan.

Use the provided plan as guidance.
Avoid exploring unrelated files unless necessary.
Keep the implementation focused.

Plan:
[Paste plan]
```

---

### Workflow B: Ask web chat which files to select

1. **Copy Tree Map**
2. Paste into web chat
3. Get file recommendations → select those files in Synapse Desktop

**Prompt:**

```text
Here is the project tree.

Task:
[Describe task]

Which files are likely relevant?
Return a prioritized list and explain briefly why.
```

---

### Workflow C: Generate spec for IDE agent

1. Select files → **Copy Context**
2. Paste into web chat → get spec
3. Paste spec into IDE agent

**Prompt:**

```text
Create an implementation spec for this task.

Task:
[Describe task]

Do not write the full code. Do not return a patch.
The spec should be suitable for an IDE coding agent.

Include:
- target behavior
- files likely to change
- implementation steps
- constraints
- edge cases
- test plan
- acceptance criteria
```

---

### Workflow D: Generate Search/Replace patch

1. Select files → **Copy + Search/Replace**
2. Paste into AI chat → get patch blocks
3. Paste response into **Apply** tab → preview diff → apply

**Prompt:**

```text
Implement this focused change.

Return only Search/Replace blocks.
Keep the patch small and minimal.

Task:
[Describe task]
```

---

### Workflow E: Review git diff

1. Choose **Git Diff** mode → copy diff
2. Paste into AI web chat

**Prompt:**

```text
Review this git diff.

Focus on:
- correctness
- edge cases
- security issues
- performance risks
- missing tests
- maintainability

Return findings by severity.
```

---

### Workflow F: Code understanding and architecture analysis

1. Select relevant files → **Copy Context**
2. Paste into web chat

**Prompt:**

```text
Analyze the selected code context.

Explain:
1. The main responsibility of this module
2. How the important files relate to each other
3. The main data flow
4. The most important functions/classes
5. Possible design issues
6. What files I should inspect next if I want to modify this feature

Do not write implementation code.
```

---

### Workflow G: Code review

1. Select files to review → **Copy Context**
2. Paste into web chat

**Prompt:**

```text
Review the selected code context.

Focus on:
- correctness
- maintainability
- architecture
- edge cases
- tests
- security risks

Do not rewrite the code.
Return actionable findings.
```

---

### Workflow H: Bug analysis

1. Select suspected files → **Copy Context**
2. Paste into web chat with bug description

**Prompt:**

```text
Analyze the selected code for this bug:

[Bug description]

Do not write a patch yet.

Return:
1. Likely root cause
2. Relevant files
3. Reasoning
4. Fix strategy
5. Tests to confirm the fix
6. Possible side effects
```

## Environment variables & CLI Options

### Environment Variables
```bash
SYNAPSE_DEBUG=1          # Enable detailed debug logging
```

### CLI Arguments
```bash
--no-license             # Bypass the license verification checks
```

## License

MIT License.

See [LICENSE](LICENSE).
