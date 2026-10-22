#!/usr/bin/env python3
"""Apply safe, idempotent command delivery and Clear Background fixes."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
repo = root / "app/src/main/java/com/example/manager/SecurityRepository.kt"
text = repo.read_text()

old = '''        addCommand(cmd)

        if (!targetToken.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {'''
new = '''        // Keep the first write local-only; addCommand() also writes PENDING to Firebase,
        // which can overwrite a fast Client acknowledgement with stale PENDING state.
        _commands.update { current -> listOf(cmd) + current.take(49) }

        if (!targetToken.matches(Regex("^[A-HJ-NP-Z2-9]{8}$")))'''
if old in text:
    text = text.replace(old, new, 1)
    print("Fixed duplicate Firebase command write.")
elif "addCommand(cmd)" not in text[text.find("fun sendRemoteCommand"):text.find("private var activeHistoryToken")]:
    print("sendRemoteCommand has no duplicate addCommand(cmd) write; leaving its current implementation intact.")
elif "Keep the first write local-only" in text:
    print("Duplicate Firebase command write was already fixed.")
else:
    raise SystemExit("Unrecognized sendRemoteCommand implementation; refusing unsafe modification.")

old = '''                if (current != null && current.status == CommandStatus.PENDING) {'''
new = '''                if (current != null && current.status in setOf(
                        CommandStatus.PENDING, CommandStatus.RECEIVED, CommandStatus.RUNNING
                    )) {'''
if old in text:
    text = text.replace(old, new, 1)
    print("Extended timeout to cover commands stuck in RECEIVED/RUNNING.")
elif "CommandStatus.RECEIVED, CommandStatus.RUNNING" in text:
    print("Command timeout already covers RECEIVED/RUNNING.")
else:
    print("No matching timeout guard found; leaving existing timeout logic intact.")
repo.write_text(text)

handler = root / "app/src/main/java/com/example/manager/AgentCommandHandler.kt"
text = handler.read_text()
if "No target app selected on Client" not in text:
    marker = "                CommandType.CLEAR_BACKGROUND_PROCESSES -> {"
    start = text.find(marker)
    end = text.find("\n                CommandType.LOCATE_DEVICE -> {", start)
    if start < 0 or end < 0:
        raise SystemExit("Could not safely locate Clear Background command block.")
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
    print("Limited Clear Background to the selected app.")
else:
    print("Selected-app Clear Background behavior already present.")
handler.write_text(text)
