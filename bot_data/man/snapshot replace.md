Uses a snapshot, but removes all of the user's roles or role's members before applying the Snapshot. This can be used to start with a clean slate, such as if a user leaves and rejoins and bots assign roles on join.

Arguments:
* `user_or_role`: The user or role to use the snapshot of.

Member Format:
* Individual User: `@user` / `UserID` / `Username#XXXX` / `Nickname` / `Username` (if they do not have a nickname)
* Role: `@role` / `"Role Name"` (Quotation escape any role names with spaces)

Examples:
* `{prefix}snapshot replace Gamer`
* `{prefix}snapshot replace @PokestarBot#9763`
