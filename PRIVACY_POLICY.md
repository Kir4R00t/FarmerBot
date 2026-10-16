# FarmerBot Privacy Policy

Last updated: October 16, 2026

This policy describes the FarmerBot instance operated by the maintainers of the
[FarmerBot repository](https://github.com/Kir4R00t/FarmerBot). Independently hosted
copies are operated by their respective owners, whose data practices may differ.

## Data received and purposes

FarmerBot receives Discord data according to the permissions and gateway intents
granted to it. Its current configuration requests all Discord gateway intents;
Discord settings and approvals determine which events it actually receives.
Discord's client library may hold server, channel, member, and user information
in memory to operate the connection.

The bot uses:

- Command names, selected options, button interactions, and Discord user, server,
  channel, and message identifiers to answer commands and operate menus. A menu
  stores its invoking user's ID in memory to limit who can control it; its
  interaction timeout is five minutes.
- Message content, the presence of attachments, author identifiers, and channel
  identifiers to apply price-check rules and respond to the configured
  developer's `ping`. The moderation code checks for a trade URL in the text;
  it does not download or analyze attachment contents. A moderation reminder
  publicly mentions the author, and the original message may be deleted.
- Server names and IDs in startup logs, plus operational events and error details
  to diagnose failures and maintain the service.
- Information you voluntarily provide when contacting the maintainer to handle
  your support or privacy request.

## Storage and retention

The application does not implement a persistent database of Discord users,
message histories, or command histories. Discord data used for interactions and
client caches is held in process memory and released as those objects expire or
the process restarts. A menu timeout ends interaction handling; it is not a
promise that every related object is immediately erased.

Operational logs can persist in hosting or container logs. The application does
not implement automatic log deletion or a fixed retention period. Contact the
maintainer to ask about retained records or request deletion. Support messages
may remain in Discord according to Discord's and the support server's settings.
Public bot responses remain in Discord until deleted there.

The bot also caches market snapshots in memory and reads snapshots stored in
Cloudflare R2. These are market datasets, not a database of Discord interactions.

## Sharing and external services

Discord processes commands, messages, responses, and interactions as the platform
provider. Bot replies and moderation reminders are visible to people who can
access the destination channel, except where Discord marks a response private.

The bot requests market information from poe2scout, random images from The Cat
API, and market snapshots from Cloudflare R2. Those requests do not intentionally
include Discord message contents or Discord user identifiers. Providers receive
normal connection information, such as the bot server's IP address and request
parameters. Images and external links may be loaded through Discord or your
client under the relevant provider's policies.

Hosting providers may process operational logs and network traffic to run the
bot. Data may also be disclosed when legally required. FarmerBot does not sell
Discord user data or use it for advertising or AI model training.

Provider information: [Discord](https://discord.com/privacy),
[Cloudflare](https://www.cloudflare.com/privacypolicy/),
[poe2scout](https://poe2scout.com/), and
[The Cat API](https://thecatapi.com/).

## Choices, requests, and contact

You can stop invoking the bot. In a server where it remains installed, it can
still receive events permitted by Discord. Server administrators can restrict
its channel access, revoke permissions, or remove it.

For privacy questions or requests to access, correct, or delete information held
by the maintainer, contact the bot maintainer through
[xfarmerx's Discord server](https://discord.com/invite/bsjQV4tFMf). Ask a moderator
to connect you with the maintainer privately; do not post sensitive information
in public channels or GitHub issues. Include only the identifiers needed to find
the relevant record. The maintainer may need to verify that a request relates to
you. Applicable law may provide additional rights, including the right to
complain to a data protection authority.

FarmerBot is intended for people eligible to use Discord under its terms and
applicable age requirements. Report suspected collection of a child's personal
data through the same private contact route.

## Updates

Changes to this policy will be published here with an updated date. Material
changes to data handling should be reflected in this policy before they take
effect.
