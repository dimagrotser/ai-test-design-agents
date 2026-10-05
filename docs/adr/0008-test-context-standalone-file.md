# Test Context in a separate Corpus Manifest

A real Jira ticket or GitHub issue has no target, Nominal Input or Outcome Keys, so these do not belong in a Story. They live in the Corpus Manifest, together with the SUT Config, the split and the class of each Story. Agents receive only the Test Context from it, never the split, class or SUT Config. The Story format is a title, text and a `## Acceptance criteria` section with lines like `- AC-1: ...`, parsed deterministically so that `FileSource` and the later `GitHubIssuesSource` read the same layout.

In v1 the Test Context is mandatory for every Story. The path where the Test Designer proposes its own Nominal Input and Outcome Keys, with no executor available, is part of the `GitHubIssuesSource` ticket.

## Considered Options

Putting these fields in the Story front matter: rejected, because it would couple the `RequirementsSource` port to eval needs and tempt me to shape Stories around the eval.
