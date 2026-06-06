# Frontend Design

## Chat Bubble System

All chat message rendering lives under `apps/web/components/chat/`.

```
apps/web/components/chat/
  MessageBubble.tsx          ← thin role-based dispatcher (entry point for chat pages)
  bubbles/
    BubbleShell.tsx          ← shared avatar + alignment layout wrapper
    DynamicSyntaxHighlighter.tsx  ← lazy-loaded Prism highlighter (shared)
    UserBubble.tsx           ← role: "user"
    AssistantBubble.tsx      ← role: "assistant" (markdown + AnalysisCard + streaming dots)
    SqlQueryBubble.tsx       ← role: "tool"
    AskUserBubble.tsx        ← role: "ask_user"
    JobApprovalBubble.tsx    ← role: "job_approval"
    JobFilesBubble.tsx       ← role: "job_files"
```

**`MessageBubble`** receives a `ChatMessage` and switches on `message.role` to render the
correct variant. It contains no layout or rendering logic of its own.

**`BubbleShell`** is the shared layout contract for all bubble variants. Props:

| Prop | Type | Default | Purpose |
|---|---|---|---|
| `side` | `"left" \| "right"` | required | Message alignment |
| `avatar` | `React.ReactNode` | required | Avatar circle content |
| `avatarBorder` | `string?` | — | Optional border class, e.g. `"border-emerald-900/40"` |
| `avatarBg` | `string?` | `"bg-[#0c0c14]"` | Avatar circle background |
| `children` | `React.ReactNode` | required | Message content |
| `timestamp` | `string?` | — | ISO string → rendered as locale time |
| `maxWidth` | `string?` | `"max-w-[78%]"` | Content column max width |

## Adding a New Bubble Variant

1. Create `apps/web/components/chat/bubbles/<RoleName>Bubble.tsx`
2. Accept `{ message: ChatMessage }` as props (extend if extra callbacks are needed)
3. Render content wrapped in `<BubbleShell side="left|right" avatar={...}>...</BubbleShell>`
4. Add a new `if (message.role === "<role>")` branch in `MessageBubble.tsx`
5. Extend `ChatMessage` in `apps/web/types/chat.ts` with any new fields the variant needs

Do **not** duplicate the avatar circle markup — always delegate layout to `BubbleShell`.
