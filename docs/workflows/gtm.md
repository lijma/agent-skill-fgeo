# GTM Workflow

fgeo is intended to be used through an AI agent, but every step is a CLI command.
That keeps the content system inspectable, repeatable, and recoverable.

## 1. Orient

Start by checking what already exists:

```bash
fgeo project list
fgeo status <project>
fgeo content list --project <project>
```

The agent should also read `.fcontext/_README.md` and `fcontext topic list` to
understand the current product context and previous go-to-market decisions.

## 2. Confirm Strategy

Strategic choices should be proposed before execution:

- Which goal matters now?
- Which platforms fit the product and audience?
- What cadence is realistic?
- How many assets are needed per platform?

After confirmation, record them:

```bash
fgeo goal add <project> "goal title"
fgeo platform add <project> devto --directions "tutorial,architecture" --pace "2/month"
fgeo plan create <project> cold-start --strategy "..."
fgeo plan assign <project> cold-start devto --direction tutorial --target 3
```

## 3. Create Platform-Native Content

Before writing, the agent should check:

```bash
fgeo brand show
fgeo style show <platform>
```

If brand or style is missing, the agent should ask the user to define it first.
The CLI stores the result:

```bash
fgeo brand set voice "clear, practical, product-led"
fgeo style add devto --desc "Developer tutorial" --formula "hook -> pain -> solution -> code -> CTA"
```

## 4. Register Content

After the user approves a saved draft:

```bash
fgeo content register <file> \
  --project <project> \
  --platform <platform> \
  --plan <plan> \
  --direction <direction> \
  --type article \
  --status draft
```

Every registered item should have project, platform, direction, and type.

## 5. Monitor Progress

```bash
fgeo status <project>
fgeo plan show <project> <plan>
```

Progress is calculated from published content against plan assignments.

