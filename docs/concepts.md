# Core Concepts

fgeo models go-to-market work as a content operations graph.

## Project

A project is the thing being promoted.

Examples:

- a developer tool
- a SaaS product
- an open source framework
- a personal IP or creator brand

Commands:

```bash
fgeo project create <name> --desc "..."
fgeo project list
fgeo project show <name>
```

## Goal

A goal describes what the project is trying to achieve.

Examples:

- Help developers understand the problem.
- Build credibility in an English developer community.
- Launch a new feature through a sequence of platform-native posts.

Commands:

```bash
fgeo goal add <project> "goal title"
fgeo goal list <project>
fgeo goal set <goal-id> status achieved
```

## Plan

A plan is a campaign or operating strategy. It can be connected to a goal and
assigned to multiple platforms.

Commands:

```bash
fgeo plan create <project> <plan-name> --strategy "..."
fgeo plan assign <project> <plan-name> <platform> --direction tutorial --target 3
fgeo plan show <project> <plan-name>
```

## Platform

A platform is a distribution channel for a project. Each platform has its own
directions, cadence, and publishing metadata.

Commands:

```bash
fgeo platform add <project> devto --directions "tutorial,architecture" --pace "2/month"
fgeo platform show <project> devto
fgeo platform set <project> devto platform_secret <api-key>
```

## Content

Content is an atomic asset. In fgeo, each adapted version is tracked as its own
content item, because a DEV.to article, Medium article, WeChat post, Bluesky
post, and Juejin pin are different platform-native artifacts.

Commands:

```bash
fgeo content register <file> --project <project> --platform <platform> --direction <direction>
fgeo content list --project <project> --status draft
fgeo content show <content-id>
```

## Brand and Style

Brand is global author identity. Style is platform-specific writing guidance.

Commands:

```bash
fgeo brand show
fgeo brand set voice "clear, opinionated, practical"

fgeo style add devto --desc "Developer tutorial style" --formula "hook -> pain -> solution -> code -> CTA"
fgeo style show devto
```

