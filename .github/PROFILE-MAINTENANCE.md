# Profile maintenance

The README keeps the animated Valleytech / Black Wire banner, guide preview, project links and latest uploads. Keep all links public and never add private repository details or credentials.

## YouTube updates

`Latest YouTube uploads` runs every six hours and can be started manually from Actions. It reads the public channel feed; it does not upload or publish videos.

YouTube intermittently returns HTTP 404 for a working channel feed. The old workflow had no retries and reported these brief outages as failures. The replacement uses four bounded attempts, validates the channel and video identifiers, escapes titles and changes only the marked video block. The first link is now on a separate line from its marker, fixing the raw Markdown that previously appeared on the profile.

If the feed is unavailable, the last good list stays in place. Runs within 72 hours of the last successful check finish with a warning and a step summary. If the outage lasts longer, the job fails so persistent problems still get attention. No notification preferences are disabled. `assets/youtube.json` records the public feed's last successful check and entries.

Run `python3 -m unittest discover -s tests` before changing the updater. The workflow runs these tests too. README marker/configuration errors fail immediately, and concurrent refreshes are serialized.

## Visuals and links

The guide preview is a real app screenshot. Refresh it when the app layout changes. The banner honors reduced-motion preferences; original logos remain unchanged. Social links, badges and the contribution snake remain in place. GitHub renders the Markdown, so verify the published profile after an edit, including the first YouTube link.
