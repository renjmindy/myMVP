# Chapter 5 | Automation Tasks and Tool Integration

## Chapter Positioning

Chapters 3 and 4 addressed "human-AI collaboration" scenarios — you were present, and the AI assisted you in completing tasks. Chapter 5 moves into the technical deep end of the course: **letting Claude Code help you build automated systems that can run independently, run repeatedly, and connect to the outside world**. This is the pivotal leap from "using AI to get work done" to "using AI to build systems."

By the end of this chapter, learners should be able to:

1. Turn a manually repeated workflow into a script that can run independently;
2. Understand the basic principles of MCP (Model Context Protocol), and independently install and use an MCP Server;
3. Use MCP to connect Claude Code to a broader range of external tools and data sources;
4. Build an intuitive knowledge base of MCP use cases through 10 illustrated tutorial examples;
5. Connect Claude Code to their own existing business services/systems;
6. Use scheduled tasks to have scripts run automatically without supervision;
7. Use the Hooks mechanism to make the entire automated workflow more controllable, observable, and interventable;
8. Assemble all of the above techniques into two complete hands-on case studies — an automated daily report system, and an automated video content pipeline — while clearly understanding the capability limits of a local-machine solution, and how the shape of a human review checkpoint changes between a factual/internal pipeline and a creative/public-facing one.

This chapter has a high knowledge density and represents the highest technical bar in the entire course. Learners are advised to complete the prerequisite chapters (especially the commands and security mechanisms in Chapters 1 and 2) before proceeding.

## Suggested Schedule

| Session | Title | Suggested Duration | Format |
|---|---|---|---|
| 5.1 | From Conversation to Script: Letting Claude Code Help You Build Your First Automation Tool | 30 minutes | Hands-on walkthrough |
| 5.2 | Get Started with MCP in 3 Minutes: Installing Your First MCP Server | 20 minutes | Guided hands-on |
| 5.3 | Connecting Claude Code to Tools via MCP | 25 minutes | Lecture + hands-on |
| 5.4 | Claude-MCP: 10 Illustrated Automation Tutorials | 30 minutes | Case walkthrough |
| 5.5 | Tool Integration: Connecting Claude Code to Your Existing Services | 30 minutes | Hands-on walkthrough |
| 5.6 | Scheduled Automation: Letting Scripts Run Themselves | 25 minutes | Hands-on walkthrough |
| 5.7 | Hooks Practical Guide: Making AI Workflows More Controllable | 30 minutes | Hands-on walkthrough |
| 5.8 | Hands-On: Automated Daily Report System | 35 minutes | Hands-on walkthrough |
| 5.9 | Hands-On: Automated Video Content Pipeline (Script → Voiceover → Short-Form Video) | 35 minutes | Hands-on walkthrough (chapter finale) |

The chapter runs approximately 4.3 hours in total. It's recommended to split it into 3–4 separate class sessions (5.1 as a standalone warm-up; 5.2–5.4 bundled as an "MCP special session"; 5.5–5.7 bundled as a "shipping and controllability" session; 5.8–5.9 bundled as a closing pair of hands-on case studies, one factual/internal and one creative/public-facing).

## Prerequisites for Learners

- Have completed Chapters 1 and 2, and are comfortable with basic terminal operations, environment variable configuration, and permission modes;
- It is recommended that learners have at least one "recurring manual task" of their own to use as a practice subject (such as regularly organizing a folder or regularly pulling data from a source);
- 5.5 requires learners to have information about a service/system they already use (such as an internal company API or a frequently used SaaS tool account) for the hands-on connection demo.

## Chapter Deliverables / Success Criteria

After completing this chapter, learners should produce:

- [ ] An automation script that can run independently and solves a real recurring task of their own;
- [ ] Successful installation and invocation of at least one MCP Server;
- [ ] At least one completed hands-on exercise connecting to an external tool via MCP;
- [ ] One completed connection integration with a service they already own;
- [ ] A configured scheduled task, verified to run the script automatically without supervision;
- [ ] At least one configured Hook, verified to fire correctly when the specified event is triggered;
- [ ] A complete end-to-end automated daily report system (5.8), along with a clear articulation of why this system currently cannot achieve "the computer is off, but the AI is still working," and how Section 6.5 of Chapter 6 will close that gap;
- [ ] A working draft of an automated video content pipeline (5.9) that reaches a reviewable draft video, with an explicit human-approval checkpoint before any publish step — and a clear articulation of why that checkpoint should stay manual, unlike the anomaly check in 5.8.

## Instructor Notes

- This chapter has a high technical bar — take it slowly, and reserve ample time in each hands-on segment for "follow-along and troubleshooting." Don't rush the pace;
- The MCP ecosystem evolves quickly. The specific MCP Servers referenced in 5.2–5.4 should be verified before class to confirm they're still available and check whether better alternatives have emerged;
- 5.6 involves system-level scheduled task configuration (such as cron / Task Scheduler), so separate operating guides for macOS and Windows need to be prepared;
- Throughout the chapter, emphasize that "automation = a broader scope of permissions + less human involvement." Security awareness needs to be higher than in previous chapters, and the Hooks mechanism in 5.7 exists precisely to preserve controllability alongside automation — make sure to clearly explain this underlying logic;
- 5.8 is the closing hands-on exercise for this chapter. Be sure to honestly tell learners about the limitation that "local scheduled tasks depend on the computer being powered on" — don't overstate the capability of a local-machine solution, and correctly direct expectations about "truly device-independent" execution toward Section 6.5 of Chapter 6.
