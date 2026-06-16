# Publishing

`fgeo publish content <id>` is the single entry point for publishing. It reads
the content metadata, detects the platform, and routes to the correct publisher.

## Commands

```bash
fgeo publish list --project <project>
fgeo publish content <content-id>
fgeo publish task list
fgeo publish task show <task-id>
fgeo publish task done <task-id>
```

## Platform Behavior

| Platform | Behavior |
| --- | --- |
| blog | Copy or Git PR flow, depending on platform `publish_url`. |
| Medium | Browser automation creates a Medium draft. |
| WeChat | Browser automation creates a WeChat official account draft. |
| Bluesky | AT Protocol API publishes immediately. |
| DEV.to | Forem API creates a draft. |
| Juejin | Cookie-based browser/API flow creates a draft. |
| Juejin Pin | Publishes a short pin. |
| Other | Records status and URL metadata. |

## Blog Publishing

Configure a blog repo:

```bash
fgeo platform set <project> blog publish_url https://github.com/user/blog.git
```

Then publish:

```bash
fgeo publish content <content-id>
```

The Git flow creates a branch, commits the post, pushes it, and attempts to open
a pull request with `gh`.

## API Credentials

Some platforms need credentials:

```bash
fgeo platform set <project> bluesky bsky_handle your.handle
fgeo platform set <project> bluesky platform_secret <app-password>
fgeo platform set <project> devto platform_secret <api-key>
```

Medium, WeChat, and Juejin use browser session cookies instead of API keys.

## Completing Tasks

Draft-based publishers create a publish task. After the user reviews and
publishes manually on the platform:

```bash
fgeo publish task done <task-id>
```

This marks the task as complete and updates the content status.

