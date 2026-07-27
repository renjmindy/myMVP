# Chapter 1｜Quick Start and Safe Usage

## Chapter Positioning

This is the "foundation" chapter of the entire course. After completing this chapter, students should be able to:

1. Clearly explain the fundamental difference between Claude Code and ordinary chat tools (ChatGPT / the Claude.ai chat box);
2. Complete the installation, login, and first run of Claude Desktop and Claude Code CLI on their own computer;
3. Know how to safely connect to third-party / relay APIs, and understand the associated risks;
4. Proficiently use daily high-frequency commands, turning "chatting with AI" into "using AI to get work done";
5. Establish basic safe-usage habits (permission modes, key management, confirmation before dangerous operations).

This chapter does not involve producing any specific project deliverables. Its purpose is to clear away the three major obstacles of "can't install it, don't know how to use it, afraid to use it," laying the groundwork for the hands-on practice that begins in Chapter 2.

## Lesson Schedule (Suggested)

| Lesson | Title | Suggested Duration | Format |
|---|---|---|---|
| 1.1 | What Is Claude Code: From Chat Tool to Working Agent | 20–25 minutes | Lecture + case demonstration |
| 1.2 | Claude Desktop Cowork and Code Basic Usage | 25 minutes | Lecture + hands-on |
| 1.3 | Claude Code CLI Installation and First Launch (includes a zero-basics terminal primer) | 30 minutes | Step-by-step hands-on |
| 1.4 | Claude Desktop and Claude Code CLI Third-Party API Integration | 25 minutes | Lecture + hands-on + safety tips |
| 1.5 | Claude Code Common Commands: Turning Conversation into a Controllable Workbench | 30 minutes | Hands-on deep dive |
| 1.6 | Advanced Commands and Custom Commands: Turning Claude Code into Your Own Work System | 30 minutes | Hands-on deep dive |
| 1.7 | Claude Desktop Third-Party LLM API Configuration Tutorial | 20 minutes | Step-by-step hands-on |

The whole chapter runs approximately 2.6–3.1 hours in total. It is recommended to split it across 2–3 class sessions, with students following along live for 1.3 / 1.4 / 1.7.

## Student Prerequisites

- A computer on which software can be installed (Windows / macOS / Linux are all fine), with administrator privileges;
- A usable email address, for registering an Anthropic account;
- **No command-line experience is required** — 1.3 already includes a built-in "terminal zero-basics primer," starting from opening the terminal and learning basic commands, so students with absolutely no background can keep up;
- It is recommended to have a payment-capable credit card or a third-party relay service account ready (for the hands-on work in 1.4 / 1.7).

## Chapter Deliverables / Success Criteria

After completing this chapter, students should produce:

- [ ] Claude Code CLI installed locally, with the ability to successfully run `claude` to enter the interactive interface;
- [ ] At least one completed hands-on exercise of "having Claude Code read a folder and generate a summary";
- [ ] At least one configured API access method (official or third-party relay), with keys correctly managed via `.env` / environment variables;
- [ ] The ability to independently name 5 or more commonly used slash commands and their purposes;
- [ ] The ability to state at least 3 principles of "safely using AI programming tools."

## Instructor Notes

- This chapter heavily involves "installation + environment variables." Be sure to pre-record installation demonstrations for both Windows and macOS in advance; focus the live session on macOS, and list common Windows pitfalls separately;
- Emphasize that the "permission confirmation" mechanism is the recurring safety thread throughout this chapter — don't wait until something goes wrong to bring it up;
- When covering third-party API relay services, provide only **neutral technical explanations** (how to configure base_url / api_key), without endorsing any specific brand, and remind students of the risks of data privacy and account suspension.
