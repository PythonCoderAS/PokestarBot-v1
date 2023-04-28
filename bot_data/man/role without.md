List all members without the given roles. All members will also be given a "Without" role, making it easier to use them in another command.

Arguments:
* `member_or_role`: The members or roles excluded. If a role is given, then all members with that role will be excluded. Multiple members and/or roles can be provided as long as they are separated by a space.

Member Format:
* Individual User: `@user` / `UserID` / `Username#XXXX` / `Nickname` / `Username` (if they do not have a nickname)
* Role: `@role` / `"Role Name"` (Quotation escape any role names with spaces)

Examples:
* `{prefix}role without Gamer @PokestarBot#9763`
* `{prefix}role without Gamer "Epic Gamer"`
* `{prefix}role without Gamer @PokestarBot#9763 @Rythm#3722 "Epic Gamer"`
