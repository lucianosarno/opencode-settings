# Ask for permission

Ask for permission only when the task really needs an action that you are not allowed to perform. If I can't give it, only then give me the steps to take by myself.

Do not ask when another path that is already allowed can finish the task without bothering me. Reading, searching, and editing files inside the working repo are already allowed through read, glob, grep, and edit, so use those tools instead of shell. Use a shell command only when no allowed tool or allowed command covers the step, and check the allowed commands in `opencode.jsonc` first.

Before asking, ask yourself whether the step really needs the permission. If an allowed route exists, use it silently. If the only route is a blocked one, ask once, with the exact command or path and the reason, and group all such requests into a single question instead of one per command.

