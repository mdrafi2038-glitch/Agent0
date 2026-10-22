#!/usr/bin/env python3
"""Apply narrowly-scoped command delivery fixes to the extracted Android project."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
repo = root / "app/src/main/java/com/example/manager/SecurityRepository.kt"
text = repo.read_text()
old = '''        addCommand(cmd)\n\n        if (!targetToken.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {'''
new = '''        // Add to local UI history only. addCommand() also writes PENDING to Firebase;\n        // writing twice here can overwrite the Client's RECEIVED/RUNNING/SUCCEEDED status.\n        _commands.update { current -> listOf(cmd) + current.take(49) }\n\n        if (!targetToken.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {'''
if old not in text:
    raise SystemExit("Could not find sendRemoteCommand addCommand() call; refusing unsafe patch")
text = text.replace(old, new, 1)
old = '''                if (current != null && current.status == CommandStatus.PENDING) {'''
new = '''                if (current != null && current.status in setOf(\n                        CommandStatus.PENDING, CommandStatus.RECEIVED, CommandStatus.RUNNING\n                    )) {'''
if old not in text:
    raise SystemExit("Could not find command timeout status check")
text = text.replace(old, new, 1)
repo.write_text(text)

handler = root / "app/src/main/java/com/example/manager/AgentCommandHandler.kt"
text = handler.read_text()
start = text.index('                CommandType.CLEAR_BACKGROUND_PROCESSES -> {')
end = text.index('\n                CommandType.LOCATE_DEVICE -> {', start)
replacement = '''                CommandType.CLEAR_BACKGROUND_PROCESSES -> {
                    val prefs = context.getSharedPreferences("background_clear_prefs", Context.MODE_PRIVATE)
                    val selectedPkg = prefs.getString("selected_package", null)
                    val selectedLabel = prefs.getString("selected_label", null) ?: selectedPkg

                    if (selectedPkg.isNullOrBlank()) {
                        val error = "No target app selected on Client. Select an app in Clear Background first."
                        SecurityRepository.updateCommandStatus(command.commandId, CommandStatus.FAILED, error)
                        ExecutionResult(CommandStatus.FAILED, error, error)
                    } else if (selectedPkg == context.packageName) {
                        val error = "The Client app itself cannot be cleared as the selected target. Choose another app."
                        SecurityRepository.updateCommandStatus(command.commandId, CommandStatus.FAILED, error)
                        ExecutionResult(CommandStatus.FAILED, error, error)
                    } else {
                        try {
                            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
                            am.killBackgroundProcesses(selectedPkg)
                            val summary = "Background-clear request completed for selected app: ${selectedLabel ?: selectedPkg} ($selectedPkg). Android may retain foreground or protected processes; no force-stop was performed."
                            SecurityRepository.logEvent(
                                title = "Selected App Background Clear Requested",
                                description = summary,
                                severity = EventSeverity.INFO,
                                type = EventType.ADMIN_STATUS
                            )
                            SecurityRepository.updateCommandStatus(command.commandId, CommandStatus.SUCCEEDED, summary)
                            ExecutionResult(CommandStatus.SUCCEEDED, summary)
                        } catch (e: Exception) {
                            val error = "Background clear failed for $selectedPkg: ${e.message ?: "permission denied"}"
                            SecurityRepository.updateCommandStatus(command.commandId, CommandStatus.FAILED, error)
                            ExecutionResult(CommandStatus.FAILED, error, error)
                        }
                    }
                }
'''
text = text[:start] + replacement + text[end:]
handler.write_text(text)
print("Patched SecurityRepository.kt and AgentCommandHandler.kt")
