# Test Context as a standalone file, referenced by the Corpus Manifest

A real Jira ticket or GitHub issue has no target, Nominal Input, statuses or Outcome Keys, so these do not belong in a Story. They live in a Test Context file next to the Story. The Corpus Manifest references one Test Context file per Story and adds what only the eval needs: the SUT Config, the split and the class. Agents receive only the Test Context, never the split, class or SUT Config.

The Story format is front matter with `id` and `title`, free text, and a `## Acceptance criteria` section with lines like `- AC-1: ...`. It is parsed deterministically, so `FileSource` and the later `GitHubIssuesSource` read the same layout.

Outside the eval, the design command takes a Story and a standalone Test Context file. In v1 the Test Context is mandatory for every Story. The path where the Test Designer proposes its own Nominal Input and Outcome Keys, with no executor available, is part of the `GitHubIssuesSource` ticket.

## Considered Options

Putting these fields in the Story front matter: rejected, because it would couple the `RequirementsSource` port to eval needs and tempt me to shape Stories around the eval.
