#!/usr/bin/env python3
"""Apply safe, idempotent command delivery and Clear Background fixes."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
repo = root / "app/src/main/java/com/example/manager/SecurityRepository.kt"
text = repo.read_text()
func_start = text.find("fun sendRemoteCommand")
func_end = text.find("private var activeHistoryToken", func_start)
if func_start < 0 or func_end < 0:
    raise SystemExit("Could not locate sendRemoteCommand safely.")
func = text[func_start:func_end]
old = '''        addCommand(cmd)

        if (!targetToken.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {'''
new = '''        // Local history only: do not write stale PENDING to Firebase a second time.
        _commands.update { current -> listOf(cmd) + current.take(49) }

        if (!targetToken.matches(Regex("^[A-HJ-NP-Z2-9]{8}$")))'''
if old in func:
    func = func.replace(old, new, 1)
    text = text[:func_start] + func + text[func_end:]
    print("Removed duplicate Firebase command write.")
elif "addCommand(cmd)" not in func:
    print("No duplicate addCommand(cmd) write exists; preserving current implementation.")
else:
    raise SystemExit("Unrecognized sendRemoteCommand implementation; refusing unsafe modification.")

old_timeout = "if (current != null && current.status == CommandStatus.PENDING) {"
new_timeout = """if (current != null && current.status in setOf(
                        CommandStatus.PENDING, CommandStatus.RECEIVED, CommandStatus.RUNNING
                    )) {"""
if old_timeout in text:
    text = text.replace(old_timeout, new_timeout, 1)
    print("Extended timeout to cover RECEIVED/RUNNING.")
elif "CommandStatus.RECEIVED, CommandStatus.RUNNING" in text:
    print("Timeout already covers RECEIVED/RUNNING.")
else:
    print("No matching timeout guard; preserving current implementation.")
repo.write_text(text)

handler = root / "app/src/main/java/com/example/manager/AgentCommandHandler.kt"
text = handler.read_text()
if "No target app selected on Client" not in text:
    start = text.find("CommandType.CLEAR_BACKGROUND_PROCESSES -> {")
    if start < 0:
        # Some project revisions route commands through a differently named handler.
        print("No CLEAR_BACKGROUND_PROCESSES branch found in AgentCommandHandler; leaving it unchanged.")
    else:
        next_branch = re.search(r"\n\s*CommandType\.[A-Z_]+\s*->\s*\{", text[start + 1:])
        if not next_branch:
            raise SystemExit("Could not find end of Clear Background branch safely.")
        end = start + 1 + next_branch.start()
        replacement = '''CommandType.CLEAR_BACKGROUND_PROCESSES -> {
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
