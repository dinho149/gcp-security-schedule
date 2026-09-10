# Hint prompt

The collapsed thread reply under each quiz question. Available instantly, opened
deliberately.

## What it is

The **AWS analogy only**. Enough to orient someone who knows AWS well; not enough
to hand over the answer.

```
🔁 <GCP service> ≈ <the reader's own system, from profile anchors>
<one line on where the analogy breaks down>
```

## Rules

- Anchor to the reader's own systems by name, via `profile.local.yaml` → `anchors`.
  Fall back to generic AWS only when no anchor exists.
- **Never name the correct option**, and never mention a distractor.
- Where the analogy genuinely misleads, say so — that is more useful than the
  mapping itself.
- **If the service has no AWS equivalent in `aws-gcp-map.json`, say exactly that.**
  "No AWS equivalent — this is the one you cannot reason about from AWS" is a
  legitimate and valuable hint.
- Two lines maximum.

## Example

```
🔁 Shared VPC ≈ sharing subnets through Resource Access Manager, not VPC peering.
Breaks down because the service project's instances land on the host project's
subnets, with IAM deciding who may use them.
```
